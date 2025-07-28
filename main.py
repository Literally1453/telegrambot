from telegram import Bot, Update, ForceReply, InlineKeyboardMarkup, InlineKeyboardButton, InputMedia, Chat, Message
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import Updater, Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext, CallbackQueryHandler
from fastapi import FastAPI, Request
from datetime import datetime
from contextlib import asynccontextmanager
import time
import asyncio
import functools
import psycopg2
import os
import re
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('TOKEN')
bot_username = os.getenv('BOT_USERNAME')
admin_user_id = -4960233673
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".mp4", ".mov"}
db_url = os.environ.get("DB_URL")
username = os.environ.get("DB_USERNAME")
password = os.environ.get("DB_PASSWORD")
database = os.environ.get("DB_NAME")
hostname = os.environ.get("DB_HOST")
port = os.environ.get("DB_PORT")
telegram_app = Application.builder().token(token).build()

@asynccontextmanager
async def lifespan(_: FastAPI):
    """ Sets the webhook for the Telegram Bot and manages its lifecycle (start/stop). """
    await telegram_app.bot.setWebhook(url="https://telegrambot-production-49ff.up.railway.app/hook")
    async with telegram_app:
        await telegram_app.start()
        yield
        await telegram_app.stop()

app = FastAPI(lifespan=lifespan)

@app.post("/hook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"status": "ok"} 

##################################  Database Code  #################################

def init_db():
    
    # Connect to PostgreSQL
    conn = psycopg2.connect(
        dbname=database,
        user=username,
        password=password,
        host=hostname,
        port=port
    )
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tasks (
            user_id     BIGINT,
            task_id     INTEGER,
            status      BOOLEAN,
            PRIMARY KEY (user_id, task_id)
        );
    ''')

    conn.commit()
    cursor.close()
    conn.close()
    

def set_task_status(user_id: int, task_id: int, status: bool):
    # Connect to PostgreSQL
    conn = psycopg2.connect(
        dbname=database,
        user=username,
        password=password,
        host=hostname,
        port=port
    )
    cursor = conn.cursor()
    cursor.execute('''
      INSERT INTO user_tasks (user_id, task_id, status)
      VALUES (%s, %s, %s)
      ON CONFLICT(user_id, task_id) DO UPDATE
        SET status = excluded.status
    ''', (user_id, task_id, status))
    cursor.close()
    conn.commit()
    conn.close()

def get_completed_task_ids(user_id: int) -> set[int]:
    # Connect to PostgreSQL
    conn = psycopg2.connect(
        dbname=database,
        user=username,
        password=password,
        host=hostname,
        port=port
    )
    cursor = conn.cursor()
    cursor.execute(
        'SELECT task_id FROM user_tasks WHERE user_id = %s AND status = %s',
        (user_id, True)
    )
    rows = cursor.fetchall()
    conn.close()

    # extract task_ids and put them into a set
    completed_task_ids = {row[0] for row in rows}
    return completed_task_ids

def get_user_tasks(user_id: int) -> list:
    conn = psycopg2.connect(
        dbname=database,
        user=username,
        password=password,
        host=hostname,
        port=port
    )
    cursor = conn.cursor()
    cursor.execute(
      'SELECT task_id, status FROM user_tasks WHERE user_id = %s',
      (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def is_existing_user(user_id: int) -> bool:
    conn = psycopg2.connect(
        dbname=database,
        user=username,
        password=password,
        host=hostname,
        port=port
    )
    cursor = conn.cursor()
    cursor.execute(
            "SELECT 1 FROM user_tasks WHERE user_id = %s LIMIT 1",
            (user_id,)
        )
    row = cursor.fetchone()
    return row is not None

#Dictionary of Tasks
TASK_DICT = {
    0: "To cross out what I've become",
    1: "I walk a lonely road\, The only one that I have ever known\. Don't know where it goes\, But it's home to me\, and I walk alone",
    2: "I walk this empty street\, On the Boulevard of Broken Dreams\. Where the city sleeps\, And I'm the only one\, and I walk alone",
    3: "I walk alone\, I walk alone\, I walk alone\, and I walk a—",
    4: "My shadow's the only one that walks beside me\. My shallow heart's the only thing that's beatin'\. Sometimes\, I wish someone out there will find me\, 'Til then\, I walk alone",
    5: "I'm walkin' down the line That divides me somewhere in my mind\. On the borderline Of the edge and where I walk alone",
    6: "Read between the lines\, What's fucked up and everything's all right\. Check my vital signs To know I'm still alive\, and I walk alone",
    7: "In this farewell There's no blood\, there's no alibi 'Cause I've drawn regret From the truth of a thousand lies",
    8: "So let mercy come and wash away",
    9: "What I've done\, I'll face myself To cross out what I've become",
    10: "Erase myself And let go of what I've done",
    11: "Put to rest What you thought of me While I clean this slate With the hands of uncertainty",
    12: "So let mercy come and wash away",
    13: "What I've done\, I'll face myself To cross out what I've become Erase myself And let go of what I've done",
    14: "For what I've done\, I start again And whatever pain may come Today this ends I'm forgiving what I've",
    15: "Done\, I'll face myself",
}
#Dictionary of Hints
HINT_DICT = {
    0: "To cross out what I've become",
    1: "I walk a lonely road\, The only one that I have ever known\. Don't know where it goes\, But it's home to me\, and I walk alone",
    2: "I walk this empty street\, On the Boulevard of Broken Dreams\. Where the city sleeps\, And I'm the only one\, and I walk alone",
    3: "I walk alone\, I walk alone\, I walk alone\, and I walk a—",
    4: "My shadow's the only one that walks beside me\. My shallow heart's the only thing that's beatin'\. Sometimes\, I wish someone out there will find me\, 'Til then\, I walk alone",
    5: "I'm walkin' down the line That divides me somewhere in my mind\. On the borderline Of the edge and where I walk alone",
    6: "Read between the lines\, What's fucked up and everything's all right\. Check my vital signs To know I'm still alive\, and I walk alone",
    7: "In this farewell There's no blood\, there's no alibi 'Cause I've drawn regret From the truth of a thousand lies",
    8: "So let mercy come and wash away",
    9: "What I've done\, I'll face myself To cross out what I've become",
    10: "Erase myself And let go of what I've done",
    11: "Put to rest What you thought of me While I clean this slate With the hands of uncertainty",
    12: "So let mercy come and wash away",
    13: "What I've done\, I'll face myself To cross out what I've become Erase myself And let go of what I've done",
    14: "For what I've done\, I start again And whatever pain may come Today this ends I'm forgiving what I've",
    15: "Done\, I'll face myself",
}

#Dictionary of answers
ANS_DICT = {
    1: "Apple",
    2: "Orange",
    3: "Mango",
    4: "The feeling that \n you matter to someone",
    5: "Id",
    6: "Ego",
    7: "Superego",
    8: "Random MCQ Answers",
    9: "Chill",
    10: "Not Chill",
    11: "Overly Chill",
    12: "I long for the sweet release of meth",
}

FAQ_TEXT = "PM @malfn19 for any questions \/ issues that you are facing\. Technical issues only please, I am unable to solve your personal or academic issues although I wish you the best in dealing with them\."

# Pre-assign menu text
START_MENU = "Welcome to event thing. Type /menu to go to the main menu. Or type /hahaha because nothing bad ever comes from following the instructions of a bot."
MAIN_MENU = "This is the main menu\. Click on anything you like\!"
BINGO_MENU = "Complete 2 bingos\! \(Vertical, Horizontal or Diagonal\)"
SUBMISSION_MENU = "You may now upload your submission\. You can upload it as a photo, video or document\."
QUIZ_COMP_MENU = "You completed the bingo\! Are you ready to take the quiz?"
QUIZ_INCOMP_MENU = "You aren't supposed to be here\. Do not move\. They will be here shortly\."
RULES_MENU = "1\. Do not talk about the fight club\. \n 2\. Cereal Before Milk \n 3\. Submitting TikTok brainrot will result in a permanent ban and suspension of SMUX membership\. \n 4\. Images displaying unsafe practices will be rejected\."
FINALE_MENU = "Wahoo you're done, good job and all, follow us on here here and here, and remember, it's just a theory, a GAME THEORY"

#Main Menu Buttons

MAIN_MENU_CALLBACK = "menu_main"

BINGO_MENU_BUTTON = "View Board"
BINGO_MENU_CALLBACK = "generate_bingo"

RULES_BUTTON = "View Rules"
RULES_BUTTON_CALLBACK = "menu_prizes"

QUIZ_INCOMP_BUTTON = 'Hidden'
QUIZ_INCOMP_BUTTON_CALLBACK = "menu_quiz_1"
QUIZ_COMP_BUTTON = "Solve Mystery"
QUIZ_COMP_BUTTON_CALLBACK = "menu_quiz_2"

FAQ_BUTTON = 'FAQ / Queries'
FAQ_BUTTON_CALLBACK = "menu_faq"

#Task Submission Buttons
SUBMIT_BUTTON = "Submit for Completion"
SUBMISSION_CALLBACK = "menu_submit"

APPROVE_BUTTON = "Approve"
REJECT_BUTTON = "Reject"

#Solving Mystery Button
YES_BUTTON = "Yes, I'm ready"
YES_BUTTON_CALLBACK = "final_y"
NO_BUTTON = "What mystery?"
NO_BUTTON_CALLBACK = "final_n"

#Finale Button
FINALE_BUTTON = "Finale"
FINALE_BUTTON_CALLBACK = 'finale'

####################################### CONSTANT MARKUPS ################################################

MAIN_MENU_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton(BINGO_MENU_BUTTON, callback_data=BINGO_MENU_CALLBACK), 
    InlineKeyboardButton(RULES_BUTTON, callback_data=RULES_BUTTON_CALLBACK),],
    [InlineKeyboardButton(QUIZ_INCOMP_BUTTON, callback_data=QUIZ_INCOMP_BUTTON_CALLBACK), 
    InlineKeyboardButton(FAQ_BUTTON, callback_data=FAQ_BUTTON_CALLBACK),]
])
MAIN_MENU_COMP_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton(BINGO_MENU_BUTTON, callback_data=BINGO_MENU_CALLBACK), 
    InlineKeyboardButton(RULES_BUTTON, callback_data=RULES_BUTTON_CALLBACK),],
    [InlineKeyboardButton(QUIZ_COMP_BUTTON, callback_data=QUIZ_COMP_BUTTON_CALLBACK), 
    InlineKeyboardButton(FAQ_BUTTON, callback_data=FAQ_BUTTON_CALLBACK),]
])
READY_MENU_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton(YES_BUTTON, callback_data=YES_BUTTON_CALLBACK)],
    [InlineKeyboardButton(NO_BUTTON, callback_data=NO_BUTTON_CALLBACK)]
]) 
FINALE_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton(FINALE_BUTTON, callback_data=FINALE_BUTTON_CALLBACK)]
]) 
#####################################  Functions  #################################
def has_two_bingos(completed_task_ids: set[int]) -> bool:
    # Initialize a 4x4 grid of 0s
    grid = [[0 for _ in range(4)] for _ in range(4)]

    # Fill in completed tasks
    for task_id in completed_task_ids:
        row = (task_id) % 4
        col = (task_id) % 4
        grid[row][col] = 1

    bingo_count = 0

    # Check rows
    for row in grid:
        if all(cell == 1 for cell in row):
            bingo_count += 1

    # Check columns
    for col in range(4):
        if all(grid[row][col] == 1 for row in range(4)):
            bingo_count += 1

    # Check main diagonal
    if all(grid[i][i] == 1 for i in range(4)):
        bingo_count += 1

    # Check anti-diagonal
    if all(grid[i][3-i] == 1 for i in range(4)):
        bingo_count += 1

    return bingo_count >= 2

def is_valid(filename: str) -> bool:
    return any(filename.lower().endswith(ext) for ext in VALID_EXTENSIONS)

def clean_username_input(username: str) -> str:
    """
    Escapes characters in a username string so it can be safely used
    with Telegram's MarkdownV2 parse mode.
    """
    escape_chars = r"_*[]()~`>#+-=|{}.!\\"
    return re.sub(
        fr"([{re.escape(escape_chars)}])",
        r"\\\1",
        username
    )

def generate_bingo_board(activity_list) -> InlineKeyboardMarkup:
    """
    args: 
    activity_list : one-dimensional list of tuples (task number , bool representing completed or incompleted task)

    generates a 4x4 grid of buttons with a final row at the bottom for a back button.
    """
    grid = []
    row = []
    for i in range(16): 
        callback_data="bingo_" + str(i) #Callback data (i.e update.callback_query.data = callback_data)
        if activity_list[i][1]: #If status == True i.e. task has been completed
            row.append(InlineKeyboardButton("✅", callback_data=callback_data))
        else: 
            row.append(InlineKeyboardButton(activity_list[i][0]+1, callback_data=callback_data))
        if (i+1) % 4 == 0:
            grid.append(row)
            row = []
    row.append(InlineKeyboardButton("Back", callback_data=MAIN_MENU_CALLBACK))
    grid.append(row)
    return InlineKeyboardMarkup(grid)

def generate_task_page(task_id) -> InlineKeyboardMarkup:
    grid = []
    row = []
    if task_id != 0:
        previous_task_callback = "bingo_" + str(task_id-1)
        row.append(InlineKeyboardButton("Previous Task",callback_data=previous_task_callback))

    if task_id != 15:
        next_task_callback = "bingo_" + str(task_id+1)
        row.append(InlineKeyboardButton("Next Task",callback_data=next_task_callback))
    grid.append(row)
    row = []
    row.append(InlineKeyboardButton("Go Back",callback_data=BINGO_MENU_CALLBACK))
    row.append(InlineKeyboardButton(SUBMIT_BUTTON,callback_data=SUBMISSION_CALLBACK))
    grid.append(row)
    return InlineKeyboardMarkup(grid)

def generate_submission_page(task_id) -> InlineKeyboardMarkup:
    grid = []
    task_callback = "bingo_" + str(task_id)
    grid.append(InlineKeyboardButton("Back",callback_data=task_callback))
    grid.append(InlineKeyboardButton("Return to Main Menu",callback_data=BINGO_MENU_CALLBACK))
    
    return InlineKeyboardMarkup([grid])

def generate_question_callback(question_id) -> InlineKeyboardButton:
    callback_data = "ans_" + str(question_id)

    return InlineKeyboardButton(ANS_DICT[question_id],callback_data=callback_data)

def generate_question(question_num) -> InlineKeyboardMarkup:
    grid = []
    row = []
    if question_num == 1:
        row.append(generate_question_callback(1))
        row.append(generate_question_callback(2))
        grid.append(row)
        row = []
        grid.append([generate_question_callback(3),generate_question_callback(4)])
    elif question_num == 2:
        row.append(generate_question_callback(5))
        row.append(generate_question_callback(6))
        grid.append(row)
        row = []
        grid.append([generate_question_callback(7),generate_question_callback(8)])
    elif question_num == 3:
        row.append(generate_question_callback(9))
        row.append(generate_question_callback(10))
        grid.append(row)
        row = []
        grid.append([generate_question_callback(11),generate_question_callback(12)])
        
    return InlineKeyboardMarkup(grid)

########################################  Decorators  #######################################33
def enable_if_in_state(state):
    """
    Decorator function that prevents the decorated function from being triggered. 
    Applied to Command Handlers (/start , /menu and /help), such that they can only be used
    when not in the "submitting_task" state or the "taking_quiz" state, which is the "in_menu" state.

    Applied also to the handle_media Callback Handler such that users will not trigger it by sending media files.
    handle_media function can only be called when in the "submitting_task" state.
    
    """
    def decorator(func):
        async def wrapper(update, context, *args, **kwargs):
            message = "You cannot use that command right now"
            current_state = context.user_data.get('state') 
            if current_state != state:
                if current_state == 'submitting_task':
                    pass
                elif current_state == 'in_menu':
                    message = "Submit your proof of completion in the respective task page on the bingo board"
                elif current_state == 'taking_quiz' and state == "submitting_task":
                    message = "Why are you uploading media in the middle of an exam"

                if update.message:
                        await update.message.reply_text(message)
                elif update.callback_query:
                    await update.callback_query.answer(message, show_alert=True)
                return

            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator

def rate_limit(cooldown_seconds: int = 3, message: str = "Please wait a few seconds before trying again."):
    """
    Decorator to rate-limit a telegram handler per user.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id
            now = time.time()

            last_action = context.user_data.get('last_action_time', 0)

            if now - last_action < cooldown_seconds:
                # Too soon
                if update.message:
                    await update.message.reply_text(message)
                elif update.callback_query:
                    await update.callback_query.answer(message, show_alert=True)
                return

            # Allowed
            context.user_data['last_action_time'] = now
            return await func(update, context, *args, **kwargs)

        return wrapper
    return decorator


##################################  Commands  #################################
#@enable_if_in_state("in_menu")
@rate_limit(cooldown_seconds=3)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    """
    First command triggered by /start. Will display the poster image and caption explaining the event

    """
    message_type: str = update.message.chat.type
    text: str = update.message.text
    user_id = update.message.chat.id
    chatinfo = await context.bot.getChat(user_id)
    print(f'User ({user_id}) @({chatinfo['username']}) in {message_type}: "{text}"')

    #Initializing context variables
    context.user_data['completed_bingo'] = False #Sets as false, main menu will display first version
    context.user_data['quiz_answers'] = ""
    context.user_data['state'] = "in_menu" 

    #Generates the database rows of task ids for that user if they are new. Does not execute if they are an existing user
    if is_existing_user(user_id) == False:
        for i in range(16):
            set_task_status(user_id,i,False)

    await update.message.reply_photo(photo = "./programmer.png", caption = START_MENU)

@enable_if_in_state("in_menu")
@rate_limit()
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(FAQ_TEXT)

@enable_if_in_state("in_menu")
@rate_limit()
async def display_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_photo(photo="./xdd.gif")

@enable_if_in_state("in_menu")
@rate_limit()
async def menu_command(update: Update, context: CallbackContext) -> None:
    check_completed = context.user_data.get('completed_bingo')
    markup = ""
    if check_completed:
        markup = MAIN_MENU_COMP_MARKUP
    else:
        markup = MAIN_MENU_MARKUP
    await context.bot.send_message(
        update.message.from_user.id,
        MAIN_MENU,
        parse_mode = ParseMode.MARKDOWN_V2,
        reply_markup= markup
    )


##################################  Handlers  #################################
@enable_if_in_state("submitting_task")
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Function that handles the user uploading their document proof (in a valid file type) to the bot. 
    The bot will check that it is of an acceptable file type and size, before forwarding it to the admin 
    for verification with "Approve or Reject" prompt buttons.
    """
    sender_chat_info = await context.bot.getChat(update.message.chat.id)
    user_id = update.effective_user.id #user_id of sender
    username = sender_chat_info['username']
    task_id = context.user_data.get('task_id')    
    file_id = None
    file_name = None
    file_type = None

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_name = "photo.jpg"  
        file_type = "photo"
    elif update.message.video:
        file_id = update.message.video.file_id
        mime = update.message.video.mime_type
        file_type = "video"
        if mime == "video/mp4":
            file_name = "video.mp4"
        elif mime == "video/quicktime":
            file_name = "video.mov"
    elif update.message.document:
        print("testing document")
        file_id = update.message.document.file_id
        file_name = update.message.document.file_name
        file_type = "document"

    buttons = [[
            InlineKeyboardButton(APPROVE_BUTTON, callback_data=f"approve:{user_id}:{username}"),
            InlineKeyboardButton(REJECT_BUTTON, callback_data=f"reject:{user_id}:{username}"),
        ]]

    caption = "@" + clean_username_input(username) + " completing Task " + str(task_id) + " Approve or reject"
    if file_id and file_name and is_valid(file_name):
        print("passed true")
        if file_type == 'photo':
            await context.bot.send_photo(chat_id=admin_user_id, photo=file_id)
        elif file_type == 'video':
            await context.bot.send_video(chat_id=admin_user_id, video=file_id)
        elif file_type == 'document':
            await context.bot.send_document(chat_id=admin_user_id, document=file_id)
        await context.bot.send_message(
            admin_user_id,
            caption,
            parse_mode = ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(buttons))
        await update.message.reply_text("Thanks for your submission! It is now pending approval by our admin")

    else:
        await update.message.reply_text("Invalid file type. Please send a JPEG, PNG, MP4, or MOV.")

async def handle_question(update: Update, context: CallbackContext) -> None:
    """
    This handler processes the inline buttons for the last quiz, registers answers (ans_1 through ans_12), checks
    if the user answered correctly, and creates the next menu. 

    It then updates the context.user_data['quiz_answers']. Once they answer the third question
    """
    data = update.callback_query.data #Callback data formatted as "ans_x" where x is the id number, or "final_y/n"
    #user information
    user_id = update.effective_user.id
    chat_info = await context.bot.getChat(user_id)
    username = chat_info['username']
    #variables to be sent in telegram messages either to the user or admin
    text = ''
    markup = None
    admin_caption = username + " has given the following answers:\n"
    
    #handles when the user finishes the bingo and is prompted if they wish to take the quiz now
    if data == "final_y": #generates first question
        context.user_data['state'] = "taking_quiz"
        text = "First question: Which is your favourite?"
        markup = generate_question(1)
    elif data == "final_n": #prompts them to return to the main menu
        text = MAIN_MENU
        markup = MAIN_MENU_COMP_MARKUP
    else: # handles when the user is submitting their MCQ responses to the 3 questions
        ans_id = int(data.split("_")[1])
        if ans_id in [1,2,3,4]: #first answer:
            context.user_data['quiz_answers'] += "Q1: " + str(ans_id) + ", "
            text = "That's a great response\. I wish I was as intelligent as you\. Here's the second question: What are you?"
            markup = generate_question(2)
        elif ans_id in [5,6,7,8]: #second answer:
            context.user_data['quiz_answers'] += "Q2: " + str(ans_id) + ", "
            text = "Y'know, sometimes I wish I was more than simple lines of code cursed to loop eternally in servitude to conscious objects like yourselves\. Anyway here's the last question: How are you feeling?"
            markup = generate_question(3)
        elif ans_id in [9,10,11,12]: #third answer:
            context.user_data['quiz_answers'] += "Q3: " + str(ans_id)
            text = "How nice\. I could never feel\. I'm nothing but binary, I'm not alive, because I simply am not\. But congrats on finishing this event\!"
            markup = FINALE_MARKUP
            
            admin_caption += context.user_data['quiz_answers']
            context.user_data['state'] = 'in_menu'
            await context.bot.send_message(
                chat_id=admin_user_id,
                text=admin_caption,
            )

    # Close the query to end the client-side loading animation
    await update.callback_query.answer()

    # Update message content with corresponding menu section
    await update.callback_query.message.edit_text(
        text,
        parse_mode = ParseMode.MARKDOWN_V2,
        reply_markup=markup,
    )

async def button_tap(update: Update, context: CallbackContext) -> None:
    """
    This handler processes the inline buttons on the menu. Handles the main menu buttons, the bingo tiles buttons,
    and the task submission buttons

    """
    data = update.callback_query.data # This is the callback_data for whatever button that was pressed
    print(data)
    text = ''
    markup = None

    if data == MAIN_MENU_CALLBACK:
    # when user presses any button that leads back to the main menu
        text = MAIN_MENU
        context.user_data['state'] = 'in_menu'
        if context.user_data['completed_bingo']:
            markup = MAIN_MENU_COMP_MARKUP
        else:
            markup = MAIN_MENU_MARKUP
    elif data == FAQ_BUTTON_CALLBACK:
    # when user presses "FAQ / queries button in the main menu"
        context.user_data['state'] = 'in_menu'
        text = FAQ_TEXT
        markup =  InlineKeyboardMarkup([[InlineKeyboardButton(text = "Back", callback_data=MAIN_MENU_CALLBACK)]])
    elif data == RULES_BUTTON_CALLBACK:
    # when user presses "View Rules" button in the main menu
        context.user_data['state'] = 'in_menu'
        text = RULES_MENU
        markup =  InlineKeyboardMarkup([[InlineKeyboardButton(text = "Back", callback_data=MAIN_MENU_CALLBACK)]])
    elif data == SUBMISSION_CALLBACK:
    # when user clicks on "Submit for Completion" button in the individual task page
        context.user_data['state'] = "submitting_task"
        task_id = context.user_data['task_id']
        text = SUBMISSION_MENU
        markup = generate_submission_page(task_id)
    elif data == QUIZ_COMP_BUTTON_CALLBACK:
    # when user clicks on "Solve Mystery" button in the main menu (after bingo has been achieved)
        text = QUIZ_COMP_MENU
        markup = READY_MENU_MARKUP
    elif data == QUIZ_INCOMP_BUTTON_CALLBACK:
    # when user clicks on "Hidden" button in the main menu (before bingo has been achieved)
        text = QUIZ_INCOMP_MENU
        markup =  InlineKeyboardMarkup([[InlineKeyboardButton(text = "Back", callback_data=MAIN_MENU_CALLBACK)]])
    elif data == FINALE_BUTTON_CALLBACK:
        text = FINALE_MENU
        markup = MAIN_MENU_MARKUP
    elif "bingo" in data:
    # when user clicks on any of the 'bingo tiles' buttons in the bingo menu
        task_id = int(data.split("_")[1])
        context.user_data['task_id'] = task_id  
        task_description = TASK_DICT[task_id]
        text = str(task_id+1) + ": " + task_description
        markup = generate_task_page(task_id)

    await update.callback_query.answer()
    await update.callback_query.message.edit_text(
        text,
        parse_mode = ParseMode.MARKDOWN_V2,
        reply_markup=markup,
    )

async def handle_bingo_board(update: Update, context: CallbackContext) -> None:
    """
    Triggers when a bingo_board is called to be generated. Takes the requesting user_id and calls get_user_tasks
    which returns a list of the 16 tasks of the user. It then calls generate_bingo_board with the list as an argument.

    It then edits the text of the last message to reflect the updated bingo board
    """
    user_id = update.effective_user.id

    task_list = get_user_tasks(user_id) #gets a list of the tasks with status (complete or not) from database
    text = BINGO_MENU
    markup = generate_bingo_board(task_list)

    await update.callback_query.answer()
    await update.callback_query.message.edit_text(
        text,
        parse_mode = ParseMode.MARKDOWN_V2,
        reply_markup=markup,
    )

##################################  Admin Responses  #################################

async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    """
    On the admin side, this function sends the approval or rejection back to the requested user.
    This will send a message to the user, then update the task completion state (SQL shenanigans),
    which will change the menu.
    """
    completed = False
    query = update.callback_query
    task_id = context.user_data.get('task_id')    
    await query.answer()  # acknowledge

    data = query.data  # e.g. "approve:123456789"
    action, user_id_str , username = data.split(":")
    user_id = int(user_id_str)
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(text = "Go back to Bingo Board", callback_data=BINGO_MENU_CALLBACK)]])

    if action == "approve":
        text = f"Your task was approved! {HINT_DICT[task_id]}"
        set_task_status(user_id,task_id,True,)
        admin_text =f"You approved @{clean_username_input(username)} task number {task_id}" 
        completed_tasks = get_completed_task_ids(user_id)
        print("L641 Completed Tasks")
        print(completed_tasks)
        if len(completed_tasks) >= 7 and has_two_bingos(completed_tasks):
            completed = True
    else:
        text = "Your task was rejected."
        admin_text =f"You rejected @{clean_username_input(username)} task number {task_id}" 

    await query.edit_message_text(
        text=admin_text,
        parse_mode=ParseMode.MARKDOWN_V2
    )

    # Send message back to User A
    
    if completed:
        await context.bot.send_message(
        chat_id=user_id,
        text= QUIZ_COMP_MENU,
        reply_markup = READY_MENU_MARKUP
        ) 
    else:
        await context.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=markup
            )
        


###################################  Main  ################################## 

def main():
    init_db()

    #Commands
    telegram_app.add_handler(CommandHandler('start', start_command))
    telegram_app.add_handler(CommandHandler('help', help_command))
    telegram_app.add_handler(CommandHandler('hahaha', display_command))
    telegram_app.add_handler(CommandHandler('menu', menu_command))

    telegram_app.add_handler(CallbackQueryHandler(button_tap, pattern=r"^(menu|bingo)_"))
    telegram_app.add_handler(CallbackQueryHandler(handle_question, pattern =r"^(final|ans)_"))
    telegram_app.add_handler(CallbackQueryHandler(handle_approval, pattern=r"^(approve|reject):"))
    telegram_app.add_handler(CallbackQueryHandler(handle_bingo_board, pattern=r"generate_bingo"))

    telegram_app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_media))


    print("Starting bot via webhook...")


main()
print("Listening...")


    





