from aiogram.fsm.state import State, StatesGroup

class AdminBookForm(StatesGroup):
    title = State()
    author = State()
    description = State()
    category = State()
    keywords = State()  # Added keywords qidiruv step
    audio = State()
    cover = State()
    pdf = State()
    confirm = State()

class UserRecForm(StatesGroup):
    title = State()
    author = State()
    description = State()
    category = State()
    keywords = State()  # Added keywords qidiruv step
    audio = State()
    cover = State()
    pdf = State()
    confirm = State()

class AdminState(StatesGroup):
    add_category = State()
    add_admin = State()
    add_required_channel_id = State()
    add_required_channel_title = State()
    add_required_channel_url = State()
    broadcast_text = State()
    broadcast_photo = State()
    broadcast_audio = State()
    edit_footer = State()  # Added state to edit custom footer

class UserState(StatesGroup):
    search = State()

class UserContactForm(StatesGroup):
    message = State()  # Added state to send support message to admin

class AdminReplyForm(StatesGroup):
    message = State()  # Added state to send reply to user

class UserProfileForm(StatesGroup):
    gender = State()  # Added profile completion states
    age = State()
    region = State()
    interests = State()
