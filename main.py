import os
import logging
import datetime as dt
from sqlalchemy import extract
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup
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

TOKEN = os.environ['BOTENV']



current_description = None
current_date = None
final_date = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Que puedo hacer por ti hoy? /new to create a new reminder."
    )
    
async def new_reminder(update, context):
    await update.message.reply_text('Cual es la descripcion del evento que quieres guardar?')
    return 1

async def get_description(update,context):
    global current_description
    current_description = update.message.text
    await update.message.reply_text('Que fecha? (dd/mm/yyyy) Te alertare varias veces al dia.')
    return 2

async def get_date(update, context):
    global current_date
    global final_date
    current_date = update.message.text
    if (len(current_date) != 10) or (current_date[2] != '/') or (current_date[5] != '/'):
        await context.bot.send_message(chat_id=update.effective_chat.id, text='Formato de fecha invalido. Intentalo de vuelta con este formato => dd/mm/yyyy. Conversacion terminada.')
        return ConversationHandler.END
    fecha = dt.datetime.strptime(current_date, '%d/%m/%Y').date()
    format_date = fecha.strftime('%Y-%m-%d')
    slices = format_date.split('-')
    year = int(slices[0])
    month = int(slices[1])
    date = int(slices[2])
    final_date = dt.date(year=year, month=month, day=date)
    await update.message.reply_text(f'Estan correctos estos datos? \n'
                                    f'{current_description} en fecha: {current_date}?', 
                                    reply_markup=ReplyKeyboardMarkup([['Si', 'No']], 
                                    one_time_keyboard=True
                                    )
                                )
    return 3

async def confirm_event(update, context):
    global current_description
    global final_date
    global db
    print(update.message.from_user)
    if update.message.text == 'Si' or update.message.text == 'si':
        with app.app_context():
            event_name = Event.query.filter_by(event_description=current_description).first()
        if not event_name:
            with app.app_context():
                event = Event(event_description=current_description, date=final_date)
            with app.app_context():
                db.session.add(event)
                db.session.commit()
            context.job_queue.run_repeating(notify_event, interval=((60*60) * 2), chat_id=update.message.chat_id)
        else:
            await update.message.reply_text('El evento ya existe! Prueba de vuelta con el comando /new.')
            return ConversationHandler.END
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'Event created! {current_description} on {current_date}'
        )
        return ConversationHandler.END
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text='Entendido! Cancelando operacion. Puedes agregar un nuevo evento con /new.')
        return ConversationHandler.END    

def cancel():
    return ConversationHandler.END

async def notify_event(context):
    job = context.job
    today = dt.date.today()
    
   
    with app.app_context():
        event_today = Event.query.filter(extract('day', Event.date)==today.day,
                                         extract('month', Event.date)==today.month,
                                         extract('year', Event.date)==today.year,
                                         ).all()
        if event_today:
            await context.bot.send_message(job.chat_id, text=f'Buenas bb! Hoy tienes los siguientes eventos:')
            for event in event_today:
                await context.bot.send_message(job.chat_id, text=f'{event.event_description}')

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="Sorry, I didn't understand that command."
        )

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('new', new_reminder)],
    states={
        1: [MessageHandler(filters.TEXT, get_description)],
        2: [MessageHandler(filters.TEXT, get_date)],
        3: [MessageHandler(filters.Regex("^(Si|No|si|no)$"), confirm_event)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    conversation_timeout=120,
)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
    application = ApplicationBuilder().token(TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)
    application.add_handler(conv_handler)
    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    application.add_handler(unknown_handler)
    
    application.run_polling()