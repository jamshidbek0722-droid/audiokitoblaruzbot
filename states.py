from aiogram.fsm.state import State, StatesGroup

class AdminBookForm(StatesGroup):
    title = State()
    author = State()
    description = State()
    category = State()
    audio = State()
    cover = State()
    pdf = State()
    confirm = State()

class UserRecForm(StatesGroup):
    title = State()
    author = State()
    description = State()
    category = State()
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

class UserState(StatesGroup):
    search = State()
