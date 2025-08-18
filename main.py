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
import textwrap
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
WEBHOOK = "https://telegrambot-production-49ff.up.railway.app/hook"
telegram_app = Application.builder().token(token).build()

#################################### FastAPI Setup #############################################
@asynccontextmanager
async def lifespan(_: FastAPI):
    """ 
    Manually sets the webhook for the bot and manages its lifecycle. 
    """
    await telegram_app.bot.setWebhook(url=WEBHOOK)
    async with telegram_app:
        await telegram_app.start()
        yield
        await telegram_app.stop()

app = FastAPI(lifespan=lifespan)

@app.post("/hook")
async def webhook(request: Request):
    """
    Communicates with the webhook, parsing the json data
    """
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
    """
    Changes the status of a task with task_id from a user with user_id
    """
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
    """
    Returns a set of task ids that the user with user_id has completed
    """
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

def get_status_of_task(user_id: int, task_id: int) -> bool:
    """
    Returns status for the specified user_id and task_id argument 
    """
    conn = psycopg2.connect(
        dbname=database,
        user=username,
        password=password,
        host=hostname,
        port=port
    )
    cursor = conn.cursor()
    cursor.execute(
        'SELECT status FROM user_tasks WHERE user_id = %s AND task_id = %s',
        (user_id, task_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] 

def get_user_tasks(user_id: int) -> list:
    """
    Returns a list of tuples (task_id,status) for a user with user_id has. 
    """
    conn = psycopg2.connect(
        dbname=database,
        user=username,
        password=password,
        host=hostname,
        port=port
    )
    cursor = conn.cursor()
    cursor.execute(
    'SELECT task_id, status FROM user_tasks WHERE user_id = %s ORDER BY task_id ASC',
      (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def is_existing_user(user_id: int) -> bool:
    """
    Checks if user with user_id already exists in the database
    """
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
    0: "*Pedal & Paddle* \nTake a picture of you with either your kayak or SUP equipment\. Your submission will not be accepted by the Magic Council if your equipment is handled poorly\.",
    1: "*Charity Walk* \nTake a selfie at any of the booths during the Charity Walk\. Bask in the strength of community and learn the power of empathy\. ",
    2: "*Skate Clinic* \nTake a video of yourself executing a new skate skill\. Your chosen skill can range from the most foundational or the most advanced skill \- this includes the proper fall method\. All the best\! Remember, any submissions where proper safety equipment \(i\.e\. helmet, knee and elbow guards, and hand guards\) shall be rejected\.",
    3: "*Stationary Surfing* \nTo complete this task, you will need to take a group picture with your friends after surfing\!",
    4: "*Longboard Clinic* \nTo complete this task, you will need to take a video of you and your friends longboarding\! Remember, any submissions where proper safety equipment \(i\.e\.\ helmet, knee and elbow guards, and hand guards\) shall be rejected\. Videos recorded while you are on the board are also not accepted\.",
    5: "*Garden of Colours* \nTake a selfie of you completing one of the activities at the event and post it up on your Instagram story\. Don’t forget to tag @smuxplorationcrew\! Submit a screenshot of your uploaded story to complete this task\.",
    6: "*Cable Board* \nTo complete this task, you will need to take a group picture with your friends \(or your new cable board mates\) at the wake park\.",
    7: "*Any local hike with SMUX Trekking* \nTo complete this task, you will need to take a picture or a video of a brightly coloured plant you encountered on your hike\.",
    8: "*Midnight Trek* \nTo complete this task, you will need to take a short video of yourself packing for the Midnight Trek\! Note that your submission only counts if you have attended the session organised by SMUX Trekking\.",
    9: "*Kayaking Orientation Programme* \nTo complete this task, you will need to take an OOTD video wearing your Personal Floatation Device\!",
    10: "*PCN Rideout* \nTo complete this task, take a cool photo of you, in your safety gears, and your bike\!",
    11: "*Halloween Skate* \nTo complete this task, take a video of you skating in your Halloween fit\!",
    12: "*PCN Rideout* \nTo complete this task, take a cool photo of you, in your safety gears, and your bike\!",
    13: "*Intertidal Walk at Lazarus Island* \nTo complete this task, take a picture or a video of an animal found during the intertidal walk\. ",
    14: "*Any dive with SMUX Diving* \nTo complete this task, take a picture of you on the boat making a crown with your hands after a dive\!",
    15: "*Tandem Bike* \nTo complete this task, take a picture of you and your partner in any of the following poses:",
}

TITLE_DICT = {
    0: "Pedal & Paddle",
    1: "Charity Walk",
    2: "Skate Clinic",
    3: "Stationary Surfing",
    4: "Longboard Clinic",
    5: "Garden of Colours",
    6: "Cable Board",
    7: "Local Hike",
    8: "Midnight Trek",
    9: "KOP",
    10: "PCN Rideout",
    11: "Halloween Skate",
    12: "PCN Rideout 2",
    13: "Intertidal Walk",
    14: "Any Dive",
    15: "Tandem Bike",
}

#Dictionary of Hints
HINT_DICT = {
    0: "_“I lurk where light forgets to tread, \nHalf in shadow, half in thread\.”_",
    1: "_“I am a workshop with no nails, \nA lab where mouths submit their trials\.”_",
    2: "_“I hold court with no tribunal, issue edicts with no voice, \nMy scepters are a row of marks \— neat witnesses of choice\.”_",
    3: "_“I slip through cracks to sip your tales, \nFollow whispers, ride the gales\.”_",
    4: "_“I’m dressed in storms from head to toe, \nA curious tide with nowhere to go\.”_",
    5: "_“I tame wild heat with lids and flame, \nTurn salt to gold and scraps to fame\.”_",
    6: "_“I swear no fealty to a crown, yet kings and carpenters seek me\. \nI speak in little battalions that march from zero to infinity\.”_",
    7: "_“I keep vessels that never sink, \nAnd drawers that never sleep or blink\.”_",
    8: "_“I host midnight meetings without guests, \nAnd feed a kingdom from my chest\.”_",
    9: "_“Bend my will and truth bends too; break my law and counting stops\.”_",
    10: "_“You’ll never see me when you should, \nBut I’ll know more than you thought I could\.”_",
    11: "_“I travel folded in a pocket, stand disciplined on desktop tops\.”_",
    12: "_“Follow whispers, ride the gales\.”_",
    13: "_“Follow whispers, ride the gales\.”_",
    14: "_“I tame wild heat with lids and flame, \nTurn salt to gold and scraps to fame\.”_",
    15: "_“I hold court with no tribunal, issue edicts with no voice, \nMy scepters are a row of marks \— neat witnesses of choice\.”_",
}

PERSON_DICT = {
    0: "*Evil Wizard*",
    1: "*Secret Hideout*",
    2: "*Magical Item*",
}

#Dictionary of answers
ANS_DICT = {
    0: "Measuring Tape",
    1: "Ruler",
    2: "Yardstick",
    3: "Gun",
    4: "Magic Wand",
    5: "Rulebook",
    6: "Set Square",
    7: "Food Lab",
    8: "Cafeteria",
    9: "Kitchen",
    10: "Library",
    11: "Restaurant",
    12: "Cafe",
    13: "Swimming Pool",
    14: "Malcolm",
    15: "Raph",
    16: "An Wen",
    17: "Balqis",
    18: "Yang Ling",
    19: "Nadra",
    20: "Chris",
}

FAQ_TEXT = "Message @malfn19 for any questions \/ issues that you are facing\. Technical issues only please, I am unable to solve your personal, academic or emotional issues although I wish you the best in dealing with them\."

# menu text
START_MENU = "Welcome to SMUX’s Virtual Challenge: Magic Mystery\. You should have already registered yourself with the Magic Council \- if you have not done so already, please head to @SMUXploration Crew on Instagram and register yourself at the link in the bio\. Otherwise, type /menu\."
MAIN_MENU = 'This is the main menu\. Click on "View Board" to start\!'
BINGO_MENU = "Your quest begins here\. To uncover the identity of the Evil Wizard, you must first complete the tasks below\. Remember, there is no guarantee that the BINGO line you’ve completed will contain all the hints that you will need to reveal the truth that you desire\. Take all the time you need, but you’re racing against time\. \n\n To begin, press on a task\."
SUBMISSION_MENU = "You may now upload your submission\. You can upload it as a photo, video or document\."
QUIZ_COMP_MENU = "You completed the bingo\! Are you ready to solve the magic mystery?"
QUIZ_INCOMP_MENU = "It seems like you haven't completed enough tasks\! Come back here when you're ready\."
QUIZ_FIN_MENU = "You've solved the Magic Mystery\! We hope you weren't intending on changing your answers because like a project due at 2359, all submissions are final\."
RULES_MENU = textwrap.dedent("""
            1\. Safety first\! Submissions displaying unsafe practices to yourself or others or a lack of donning proper safety equipment \(e\.g\. helmet, guards\) that the activity would require will be rejected\. \n 
            2\. Submissions must be done while participating in a SMUX activity\. \n 
            3\. Please do not upload viruses or malware as I have zero file sanitation security\. \n 
            4\. If you want to instantly win this challenge, paynow $100 to 90967606\.
            """)
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
QUIZ_FIN_BUTTON = "Mystery Solved!"
QUIZ_FIN_BUTTON_CALLBACK = "menu_quiz_3"

FAQ_BUTTON = 'FAQ / Queries'
FAQ_BUTTON_CALLBACK = "menu_faq"

#Task Submission Buttons
SUBMIT_BUTTON = "Submit"
SUBMISSION_CALLBACK = "menu_submit"

APPROVE_BUTTON = "Approve"
REJECT_BUTTON = "Reject"

#Solving Mystery Button
YES_BUTTON = "Yes, I'm ready"
YES_BUTTON_CALLBACK = "final_y"
NO_BUTTON = "What mystery?"
NO_BUTTON_CALLBACK = "final_n"

#Confirmation (of final answers) Button
CONFIRM_BUTTON = "Yes"
CONFIRM_BUTTON_CALLBACK = "final_confirm"
REDO_BUTTON = "No (Retry)"

#Finale Button
FINALE_BUTTON = "Go Back To Main Menu"
FINALE_BUTTON_CALLBACK = 'menu_finale'




####################################### CONSTANT MARKUPS ################################################

READY_MENU_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton(YES_BUTTON, callback_data=YES_BUTTON_CALLBACK)],
    [InlineKeyboardButton(NO_BUTTON, callback_data=NO_BUTTON_CALLBACK)]
]) 
CONFIRMATION_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton(CONFIRM_BUTTON, callback_data=CONFIRM_BUTTON_CALLBACK),
     InlineKeyboardButton(REDO_BUTTON,callback_data=YES_BUTTON_CALLBACK)]])
FINALE_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton(FINALE_BUTTON, callback_data=FINALE_BUTTON_CALLBACK)]
]) 

#####################################  Functions  #################################
def has_bingo(completed_task_ids: set[int]) -> bool:
    # All possible winning lines in a 4x4 bingo grid
    winning_lines = []

    # Rows
    for r in range(4):
        winning_lines.append({r * 4 + c for c in range(4)})
    # Columns
    for c in range(4):
        winning_lines.append({r * 4 + c for r in range(4)})
    # Diagonals
    winning_lines.append({0, 5, 10, 15})  
    winning_lines.append({3, 6, 9, 12})   

    # Check if any winning line is fully contained in completed_task_ids
    return any(line.issubset(completed_task_ids) for line in winning_lines)

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

def get_object_num(task_id: int) -> int:
    if task_id in [0,3,4,10,11,13]:
        person_num = 0
    elif task_id in [1,5,7,8,14]:
        person_num = 1
    else:
        person_num = 2
    return person_num

def generate_main_menu(user_id) -> tuple:
    completed_tasks = get_completed_task_ids(user_id)
    text = MAIN_MENU
    if has_bingo(completed_tasks) and len(completed_tasks) == 16:
        text = FINALE_MENU
        quiz_button = QUIZ_FIN_BUTTON
        quiz_button_callback = QUIZ_FIN_BUTTON_CALLBACK
    elif has_bingo(completed_tasks):
        quiz_button = QUIZ_COMP_BUTTON
        quiz_button_callback = QUIZ_COMP_BUTTON_CALLBACK
    else:
        quiz_button = QUIZ_INCOMP_BUTTON
        quiz_button_callback = QUIZ_INCOMP_BUTTON_CALLBACK

    markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(BINGO_MENU_BUTTON, callback_data=BINGO_MENU_CALLBACK), 
                InlineKeyboardButton(RULES_BUTTON, callback_data=RULES_BUTTON_CALLBACK),],
                [InlineKeyboardButton(quiz_button, callback_data=quiz_button_callback), 
                InlineKeyboardButton(FAQ_BUTTON, callback_data=FAQ_BUTTON_CALLBACK),]
            ])
    
    return (text, markup)

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
            row.append(InlineKeyboardButton(text=str(i+1), callback_data=callback_data))
        if (i+1) % 4 == 0:
            grid.append(row)
            row = []
    row.append(InlineKeyboardButton("Back", callback_data=MAIN_MENU_CALLBACK))
    grid.append(row)
    return InlineKeyboardMarkup(grid)

def generate_task_page(user_id,task_id) -> InlineKeyboardMarkup:
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
    if get_status_of_task(user_id,task_id) == False:
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
    for i in range(7):
        grid.append([generate_question_callback(7 * question_num - (7 - i))])
        
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
                    message = "Why are you uploading media in the middle of an exam?"

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
    context.user_data['state'] = "in_menu" 

    #Generates the database rows of task ids for that user if they are new. Does not execute if they are an existing user
    if is_existing_user(user_id) == False:
        for i in range(16):
            set_task_status(user_id,i,False)

    await update.message.reply_photo(photo = "./programmer.png", caption = START_MENU, parse_mode=ParseMode.MARKDOWN_V2)

@enable_if_in_state("in_menu")
@rate_limit()
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(text=FAQ_TEXT, parse_mode=ParseMode.MARKDOWN_V2)

@enable_if_in_state("in_menu")
@rate_limit()
async def display_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    markuplist = []
    for i in range(7):
        markuplist.append([InlineKeyboardButton(text="aaaaaaaaaaaa",callback_data=MAIN_MENU_CALLBACK)])
    markup = InlineKeyboardMarkup(markuplist)
    await context.bot.send_message(
        update.message.from_user.id,
        MAIN_MENU,
        parse_mode = ParseMode.MARKDOWN_V2,
        reply_markup= markup
    )

@enable_if_in_state("in_menu")
@rate_limit()
async def menu_command(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id #user_id of sender
    text, markup = generate_main_menu(user_id)
   
    await context.bot.send_message(
        update.message.from_user.id,
        text,
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
            InlineKeyboardButton(APPROVE_BUTTON, callback_data=f"approve:{user_id}:{username}:{task_id}"),
            InlineKeyboardButton(REJECT_BUTTON, callback_data=f"reject:{user_id}:{username}:{task_id}"),
        ]]

    caption = f"@{clean_username_input(username)} is completing Task {str(task_id+1)}: {TITLE_DICT[task_id]}"
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
        await update.message.reply_text("Thanks for your submission! It is now pending approval by the Magic Council (a.k.a our unpaid associates)")

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
        context.user_data['quiz_answers'] = ""
        text = "Select your deduced weapon:"
        markup = generate_question(1)
    elif data == "final_n": #prompts them to return to the main menu
        text, markup = generate_main_menu(user_id)
    elif data == "final_confirm": #if they confirm their submission of final answers
        for i in range(16):
            set_task_status(user_id,i,True)
        text = "Deduction received\. You will be notified of the news when the investigation closes\. Thank you for solving the Magic Mystery\!"
        markup = FINALE_MARKUP
        admin_caption += context.user_data['quiz_answers']
        context.user_data['state'] = 'in_menu'
        await context.bot.send_message(
            chat_id=admin_user_id,
            text=admin_caption,
        )
    else: # handles when the user is submitting their MCQ responses to the 3 questions
        ans_id = int(data.split("_")[1])
        if ans_id <= 6: #first answer:
            context.user_data['quiz_answers'] += f"\nWeapon: {ANS_DICT[ans_id]}, "
            text = "Select your deduced location:"
            markup = generate_question(2)
        elif ans_id > 6 and ans_id < 13: #second answer:
            context.user_data['quiz_answers'] += f"\nLocation: {ANS_DICT[ans_id]}, "
            text = "Select your deduced Evil Wizard:"
            markup = generate_question(3)
        else: #third answer:
            context.user_data['quiz_answers'] += f"\nSuspect: {ANS_DICT[ans_id]}"
            text = f"You have given the following answers: {context.user_data['quiz_answers']}\. \nIs this your final answer?"
            markup = CONFIRMATION_MARKUP   

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
    user_id = update.callback_query.from_user.id
    print(data)
    text = ''
    markup = None

    if data == MAIN_MENU_CALLBACK:
    # when user presses any button that leads back to the main menu
        context.user_data['state'] = 'in_menu'
        text, markup = generate_main_menu(user_id)
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
    elif data == QUIZ_FIN_BUTTON_CALLBACK:
    # when user clicks on "Hidden" button in the main menu (before bingo has been achieved)
        text = QUIZ_FIN_MENU
        markup =  InlineKeyboardMarkup([[InlineKeyboardButton(text = "Back", callback_data=MAIN_MENU_CALLBACK)]])
    elif data == FINALE_BUTTON_CALLBACK:
        text, markup = generate_main_menu(user_id)
    elif "bingo" in data:
    # when user clicks on any of the 'bingo tiles' buttons in the bingo menu
        task_id = int(data.split("_")[1])
        context.user_data['task_id'] = task_id
        task_description = TASK_DICT[task_id]
        if get_status_of_task(user_id,task_id):
            item = PERSON_DICT[get_object_num(task_id)]
            task_description += f"\n\nYou have completed this task\. The hint to find the {item} is: \n {HINT_DICT[task_id]}"
        else:
            task_description += "\n\nIf you are ready to complete this task, press 'Submit'\!"
        text = str(task_id+1) + ": " + task_description
        markup = generate_task_page(user_id,task_id)

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
    print(task_list)
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
    print(query)  
    await query.answer()  

    data = query.data  # e.g. "approve:123456789:username:<task_id>"
    action, user_id_str , username , task_id_str = data.split(":")
    user_id = int(user_id_str)
    task_id = int(task_id_str)
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(text = "Go back to Bingo Board", callback_data=BINGO_MENU_CALLBACK)]])
    second_text = "Good luck on your next adventure\!"

    if action == "approve":
        item = PERSON_DICT[get_object_num(task_id)]
        first_text = f"Well done in completing Activity {task_id+1}\! \nYou've earned the following clue to find the {item}: \n{HINT_DICT[task_id]}"
        set_task_status(user_id,task_id,True,)
        admin_text =f"You approved @{clean_username_input(username)}'s task {str(task_id+1)}: {TITLE_DICT[task_id]}" 
        completed_tasks = get_completed_task_ids(user_id)
        if len(completed_tasks) >= 4 and has_bingo(completed_tasks):
            completed = True
    else:
        first_text = "Your task was rejected\. It's possible that you did not follow one of the rules\. Try again\! You may also talk to the manager @malfn19 if you need clarification\."
        admin_text =f"You rejected @{clean_username_input(username)} task number {str(task_id+1)}" 

    await query.edit_message_text(
        text=admin_text,
        parse_mode=ParseMode.MARKDOWN_V2
    )

    # Send message back to User A
    
    if completed:
        await context.bot.send_message(
        chat_id=user_id,
        text= QUIZ_COMP_MENU,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup = READY_MENU_MARKUP
        )
    else:
        await context.bot.send_message(
                chat_id=user_id,
                text=first_text,
                parse_mode= ParseMode.MARKDOWN_V2
            )
        await context.bot.send_message(
                chat_id=user_id,
                text=second_text,
                reply_markup=markup,
                parse_mode= ParseMode.MARKDOWN_V2
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


    





