# my_user_id = 508617756

# async def menu_command(update: Update, context: CallbackContext) -> None:
#     """
#     Command triggered by '/menu'
#     This handler opens the main menu. The main menu includes a few buttons. Firstly, the Bingo Board button
#     that opens the bingo board. A View Prizes button that displays a message of the prizes.
#     """
#     menu_message_id = context.user_data.get('menu_message_id')

#     context.user_data['menu_message_id'] = Message.message_id

#     if menu_message_id:
#         # Try editing the existing message
#         try:
#             await context.bot.edit_message_text(
#                 chat_id=user_id,
#                 message_id=menu_message_id,
#                 text=MAIN_MENU,
#                 parse_mode=ParseMode.MARKDOWN_V2,
#                 reply_markup=MAIN_MENU_MARKUP
#             )
#             return  # done
#         except BadRequest:
#             # Message might have been deleted or is otherwise uneditable
#             pass

#     # If no previous menu, or edit failed, send a new menu
#     sent = await context.bot.send_message(
#         chat_id=user_id,
#         text=MAIN_MENU,
#         parse_mode=ParseMode.MARKDOWN_V2,
#         reply_markup=MAIN_MENU_MARKUP
#     )

#     # Save the new menu message_id
#     context.user_data['menu_message_id'] = sent.message_id