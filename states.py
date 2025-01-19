from aiogram.fsm.state import State, StatesGroup

class Form(StatesGroup):
    name = State()
    age = State()
    sex = State()
    weight = State()
    height = State()
    active = State()
    city = State()
    norma_calories = State()
    norma_water = State()

class Water(StatesGroup):
    water = State()

class Food(StatesGroup):
    food = State()
    amount = State()

class Workout(StatesGroup):
    activity_type = State()
    time = State()
