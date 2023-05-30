import threading
import logging
import time
import datetime as dt
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler,ConversationHandler, filters

# LOGGING CONFIGURATION
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# INITIALIZING
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'supersecretkey'

db = SQLAlchemy(app)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_description = db.Column(db.String(200), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    reminded = db.Column(db.Boolean, nullable=False)

TOKEN = open('token.txt', 'r').read()



current_description = None
current_date = None
final_date = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="What can I do for you today? /new to create a new reminder."
    )
    
async def new_reminder(update, context):
    await update.message.reply_text('What is the event description?')
    return 1

async def get_description(update,context):
    global current_description
    current_description = update.message.text
    await update.message.reply_text('What is the date? (dd-mm-yyyy)')
    return 2

async def get_date(update, context):
    global current_date
    global final_date
    current_date = update.message.text
    print(f'current_date  {current_date}')
    fecha = dt.datetime.strptime(current_date, '%d/%m/%Y').date()
    print(f'fecha  {fecha}')
    format_date = fecha.strftime('%Y-%m-%d')
    slices = format_date.split('-')
    year = int(slices[0])
    month = int(slices[1])
    date = int(slices[2])
    final_date = dt.date(year=year, month=month, day=date)
    print(f'format_date  {final_date}')
    await update.message.reply_text(f'Are you sure you want to create the event? {current_description} on {current_date}? Reply with yes or no')
    return 3

async def confirm_event(update, context):
    global current_description
    global final_date
    global db
    if update.message.text == 'yes':
        with app.app_context():
            event_name = Event.query.filter_by(event_description=current_description).first()
        if not event_name:
            with app.app_context():
                event = Event(event_description=current_description, date=final_date, reminded=False)
            with app.app_context():
                db.session.add(event)
                db.session.commit()
        else:
            await update.message.reply_text('Event already exists! Try again with /new.')
            return ConversationHandler.END
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'Event created! {current_description} on {current_date}'
        )
        return ConversationHandler.END
    else:
        return ConversationHandler.END    

def cancel():
    return ConversationHandler.END

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="Sorry, I didn't understand that command."
        )

## DEPRECATED
def check_events():
    while True:
        today = dt.date.today()
        print(today)
        with app.app_context():
            event_today = Event.query.filter_by(reminded=False).filter(Event.date == today).all()
            print(f'event_today => {event_today}')
            for event in event_today:
                # context.bot.send_message('Event today: ' + event.event_description)
                event.reminded = True
                db.session.commit()
                
        time.sleep(60)
        
# threading.Thread(target=check_events).start()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('new', new_reminder)],
    states={
        1: [MessageHandler(filters.TEXT, get_description)],
        2: [MessageHandler(filters.TEXT, get_date)],
        3: [MessageHandler(filters.TEXT, confirm_event)],
        4: [MessageHandler(filters.TEXT, create_event)]
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    conversation_timeout=120,
)


if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)
    application.add_handler(conv_handler)
    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    application.add_handler(unknown_handler)
    
    application.run_polling()