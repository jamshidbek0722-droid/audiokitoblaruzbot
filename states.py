from aiogram.fsm.state import State, StatesGroup

class AdminBookForm(StatesGroup):
    title = State()
    author = State()
    description = State()
    category = State()
    keywords = State()
    audio = State()
    cover = State()
    pdf = State()
    confirm = State()

class UserRecForm(StatesGroup):
    title = State()
    author = State()
    description = State()
    category = State()
    keywords = State()
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
    edit_footer = State()

class UserState(StatesGroup):
    search = State()

class UserContactForm(StatesGroup):
    message = State()

class AdminReplyForm(StatesGroup):
    message = State()

class UserProfileForm(StatesGroup):
    gender = State()
    age = State()
    region = State()
    interests = State()

class AdminEditBookState(StatesGroup):
    select = State()
    field = State()
    value = State()
    audio = State()
    pdf = State()
    cover = State()
    category = State()

class AdminCategoryLayoutState(StatesGroup):
    select = State()
    columns = State()
    order = State()

class AdminSortingState(StatesGroup):
    select = State()

# AI Switchboard State
class AdminAISettingsState(StatesGroup):
    dashboard = State()

# Menu Settings State
class AdminMenuSettingsState(StatesGroup):
    select_action = State()
    edit_row = State()
    edit_label_select = State()
    edit_label_value = State()

# User AI Recommendation Quiz
class UserAIRecommendationState(StatesGroup):
    quiz = State()

# User AI Companion Chat
class UserAIChatState(StatesGroup):
    chat = State()
