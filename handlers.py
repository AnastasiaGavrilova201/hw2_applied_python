from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.types import FSInputFile
from states import Form, Water, Food, Workout
from aiogram.fsm.context import FSMContext
import requests
import pandas as pd
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt

router = Router()
users = {}

# Обработчик команды /start
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply("Добро пожаловать! Я ваш бот. Введите /help для просмотра всех функций")

# подсказки по функциям
@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "/set_profile - установить параметры пользователя\n"
        "/log_food - записать информацию о потребленных продуктах\n"
        "/log_workout - записать информацию о тренировках\n"
        "/log_water - записать информацию о потребленной воде\n"
        "/restart_progress - сбросить прогресс по калориям и воде\n"
        "/check_progress - посмотреть прогресс по калориям и воде"
    )
    await message.reply(help_text)

# настройка профиля
@router.message(Command("set_profile"))
async def start_form(message: Message, state: FSMContext):
    await message.reply("Введите ваше имя")
    await state.set_state(Form.name)

# клавиатура для способа расчета нормы калорий и воды
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
keyboard_calc_type = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Рассчитать автоматически", callback_data="auto")],
        [InlineKeyboardButton(text="Ввести вручную", callback_data="hand")],
    ]
)
# настройка имени
@router.message(Form.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.reply("Выберите способ расчета нормы калорий и воды:",
                        reply_markup=keyboard_calc_type)

# колбеки на ответы клавиатуры
@router.callback_query()
async def handle_callback_calc_type(callback_query, state: FSMContext):
    if callback_query.data == "hand":
        await callback_query.message.reply("Введите вашу норму воды в день (мл)")
        await state.set_state(Form.norma_water)
    elif callback_query.data == "auto":
        await callback_query.message.reply("Введите ваш возраст")
        await state.set_state(Form.age)
    else:
        # коэффициент по полу для расчета нормы калорий
        coef = 5
        if callback_query.data == "female":
            coef = -161
        await state.update_data(sex=coef)
        await callback_query.message.reply("Введите ваш вес в кг")
        await state.set_state(Form.weight)

# настройка нормы воды в случае ручного ввода
@router.message(Form.norma_water)
async def process_water(message: Message, state: FSMContext):
    await state.update_data(norma_water=float(message.text))
    await message.reply("Введите вашу норму калорий")
    await state.set_state(Form.norma_calories)

# настройка нормы калорий в случае ручного ввода и фиксация данных о юзере
@router.message(Form.norma_calories)
async def process_calories(message: Message, state: FSMContext):
    norma_calories=float(message.text)
    chat_id = message.chat.id
    data = await state.get_data()
    name = data.get("name")
    user_data = {
        "name": name,
        "norma_water": data.get("norma_water"),
        "norma_calories": norma_calories,
        "progress_water": [0],
        "progress_calories": [0],
        "burned_calories": 0
    }
    users[chat_id] = user_data
    await message.reply(f"{name}, данные зафиксированы")
    await state.clear()

# клавиатура для определения пола
keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Мужской", callback_data="male")],
        [InlineKeyboardButton(text="Женский", callback_data="female")],
    ]
)
# настройка возраста для автоматического расчета калорий и воды
@router.message(Form.age)
async def process_sex(message: Message, state: FSMContext):
    await state.update_data(age=message.text)
    await message.reply("Укажите ваш пол:", reply_markup=keyboard)

# настройка веса
@router.message(Form.weight)
async def process_weight(message: Message, state: FSMContext):
    await state.update_data(weight=message.text)
    await message.reply("Введите ваш рост в см")
    await state.set_state(Form.height)

# настройка роста
@router.message(Form.height)
async def process_height(message: Message, state: FSMContext):
    await state.update_data(height=message.text)
    await message.reply("Сколько минут в день вы занимаетесь физической активностью?")
    await state.set_state(Form.active)

# настройка уровня активности
@router.message(Form.active)
async def process_active(message: Message, state: FSMContext):
    await state.update_data(active=message.text)
    await message.reply("Введите название вашего города")
    await state.set_state(Form.city)

# настройка города и фиксация данных о юзере
@router.message(Form.city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    chat_id = message.chat.id
    data = await state.get_data()
    name = data.get("name")
    user_data = {
        "name": name,
        "age": int(data.get("age")),
        "sex" : data.get("sex"),
        "weight": float(data.get("weight")),
        "height": float(data.get("height")),
        "active": int(data.get("active")),
        "city": message.text,
        "progress_water": [0],
        "progress_calories": [0],
        "burned_calories": 0
    }
    water = calc_water(user_data)
    calories = calc_calories(user_data)
    user_data["norma_calories"] = calories
    user_data["norma_water"] = water
    users[chat_id] = user_data
    await message.reply(f"{name}, данные зафиксированы.\nВаша норма колорий в день: {calories}.\nВаша норма воды в день: {water}")
    await state.clear()

# функция для получения температуры в городе через апи
def get_weather(city):
    api_key = '95a7a3c9994296d3614d4e1ebde14090'
    base_url = "http://api.openweathermap.org/data/2.5/weather?"
    base_url = base_url + "appid=" + api_key + "&units=metric" + "&q=" + city
    response = requests.get(base_url)
    x = response.json()
    return(x['main']['temp'])

# функция для расчета нормы воды
def calc_water(data):
    weight = data['weight']
    city = data['city']
    active = data['active']
    temperature = get_weather(city)
    flg = 0
    if temperature > 25:
        flg = 1
    result = 30*weight + 500*active/30 + flg*500
    return result

# функция для расчета нормы калорий
def calc_calories(data):
    weight = data['weight']
    height = data['height']
    age = data['age']
    sex = data['sex']
    active = data['active']
    coef = 1.2
    if 10 < active and active < 20:
        coef = 1.375
    elif 20 <= active and active < 30:
        coef = 1.55
    elif 30 <= active and active < 40:
        coef = 1.725
    elif 40 <= active:
        coef = 1.375
    #Формула Миффлина-Сент-Джорa
    # адаптированная под случай, когда физ активность фиксуруется за день, а не за неделю
    result = (10*weight + 6.25*height - 5*age + sex)*coef
    return result

# лорирование воды
@router.message(Command("log_water"))
async def cmd_log_water(message: Message, state: FSMContext):
    chat_id = message.chat.id
    if chat_id in users.keys():
        await message.reply("Введите кол-во употребленной воды (мл)")
        await state.set_state(Water.water)
    else:
        await message.reply("Для логирования воды заполните профиль.\nВведите /set_profile")

# запись кол-ва воды и обновление прогресса по воде
@router.message(Water.water)
async def water_amount(message: Message, state: FSMContext):
    chat_id = message.chat.id
    data = users[chat_id]
    cur_amount =data["progress_water"][-1] + int(message.text)
    left = data["norma_water"] - cur_amount
    users[chat_id]["progress_water"].append(cur_amount)
    await message.reply( f"Сегодня вы употребили {cur_amount} мл воды. Осталось {left} мл")
    await state.clear()

# логирование еды
@router.message(Command("log_food"))
async def cmd_log_food(message: Message, state: FSMContext):
    chat_id = message.chat.id
    if chat_id in users.keys():
        await message.reply("Укажите продукт/блюдо")
        await state.set_state(Food.food)
    else:
        await message.reply("Для логирования еды заполните профиль.\nВведите /set_profile")

# запись названия продукта
@router.message(Food.food)
async def food_type(message: Message, state: FSMContext):
    food = message.text.replace(' ', '+')
    await state.update_data(food=food)
    await message.reply("Укажите кол-во грамм")
    await state.set_state(Food.amount)

#апи для определения калорийности
# взято из подсказок в дз
def get_food_info(product_name):
    url = f"https://world.openfoodfacts.org/cgi/search.pl?action=process&search_terms={product_name}&json=true"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        products = data.get('products', [])
        if products:  # Проверяем, есть ли найденные продукты
            first_product = products[0]
            return {
                'flg_success': 1,
                'calories': first_product.get('nutriments', {}).get('energy-kcal_100g', 0)
            }
        return {
            'flg_success': 0
            }
    return {
            'flg_success': 0
            }
# запись кол-ва еды и обновление прогресса
@router.message(Food.amount)
async def food_amount(message: Message, state: FSMContext):
    grams = float(message.text)
    data = await state.get_data()
    food_type = data.get("food")
    chat_id = message.chat.id
    data = users[chat_id]
    response = get_food_info(food_type)
    if response['flg_success'] == 0:
        await message.reply("Извините, мы не можем найти калорийность вашего продукта/блюда.\nУкажите другой продукт")
    else:
        kcal_100g = response['calories']
        kcal_meal = kcal_100g * grams/100
        kcal_total = data["progress_calories"][-1] + kcal_meal
        left = data["norma_calories"] - kcal_total
        users[chat_id]["progress_calories"].append(kcal_total)
        await message.reply( f"Сегодня вы употребили {kcal_total} ккал. Осталось {left} ккал")
    await state.clear()

# функция для определния затраченных на тренировке калорий
def activities():
    # сайт с разными видами спорта.
    # берем оттуда кол-во потраченных калорий в час
    # в зависимости от вида спорта и веса
    url = 'https://kalkulyator-kaloriy.ru/rashod-kaloriy/'
    response = requests.get(url)
    data = []
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        activities_table = soup.find_all('table')  # .find_all('Спортивные игры и упражнения')
        for row in activities_table:
            columns = row.find_all('td')
            for i in columns:
                el = str(i).replace('/', '').replace('<td>', '').replace('<strong>', '')
                data.append(el)
    data = data[2:]
    rows = []
    headers = [data[i].strip() for i in range(6)]
    for i in range(6, len(data), 6):
        row = [data[i]] + [data[j] for j in range(i + 1, i + 6)]
        rows.append(row)
    df = pd.DataFrame(rows, columns=headers)
    return df

# логирование тренировок
@router.message(Command("log_workout"))
async def cmd_log_workout(message: Message, state: FSMContext):
    chat_id = message.chat.id
    if chat_id in users.keys():
        await message.reply("Укажите вид тренировки")
        await state.set_state(Workout.activity_type)
    else:
        await message.reply("Для логирования тренировок заполните профиль.\nВведите /set_profile")

# запись типа активности
@router.message(Workout.activity_type)
async def log_workout_type(message: Message, state: FSMContext):
    await state.update_data(activity_type=message.text)
    await message.reply("Укажите длительность тренировки в минутах")
    await state.set_state(Workout.time)

# запись времени активности, расчет калорий и обновление прогресса
@router.message(Workout.time)
async def message_log_workout_time(message: Message, state: FSMContext):
    time = float(message.text)
    data = await state.get_data()
    activity = data.get("activity_type")
    data_act = activities()
    chat_id = message.chat.id
    user_data = users[chat_id]
    column = '70 кг'
    if 'weight' in user_data.keys():
        weight = user_data['weight']
        if weight < 65:
            column = '60 кг'
        elif 75 <= weight and weight < 85:
            column = '80 кг'
        elif 85 <= weight and weight < 95:
            column = '90 кг'
        elif weight >= 95:
            column = '100 кг'
    kcal = int(data_act[data_act['Вид спорта, упражнения'] == activity][column])
    train_kcal = time*kcal/60
    add_water = 200*time/30
    await message.reply(f"Вы потратили {train_kcal} ккал за тренировку.\nВыпейте {add_water} мл воды.")
    users[chat_id]['burned_calories']+=train_kcal
    await state.clear()

# просмотр прогресса по воде и калориям
@router.message(Command("check_progress"))
async def cmd_check_progress(message: Message):
    chat_id = message.chat.id
    if chat_id in users.keys():
        data = users[chat_id]
        kcal_norma = data['norma_calories']
        water_norma = data['norma_water']
        water = data['progress_water']
        kcal = data['progress_calories']
        await message.reply("Прогресс по воде:\n"
                            f"Употреблено {water[-1]} мл\n"
                            f"Цель {water_norma} мл\n"
                            f"Осталось {water_norma - water[-1]} ккал\n\n"
                            "Прогресс по калориям:\n"
                            f"Употреблено {kcal[-1]} ккал\n"
                            f"Цель {kcal_norma} ккал\n"
                            f"Осталось {kcal_norma-kcal[-1]} ккал\n"
                            f"Сожжено {data['burned_calories']} ккал\n")

        n = max(len(kcal), len(water))
        # выводим график, если есть прогресс
        if n > 1:
            water_norma_list = [water_norma]*n
            kcal_norma_list =  [kcal_norma]*n
            # Создание графика
            plt.figure()
            plt.plot(water_norma_list, label='Норма калорий (ккал)')
            plt.plot(kcal_norma_list, label='Норма воды (мл)')
            plt.plot(water, label='Потребление калорий (ккал)')
            plt.plot(kcal, label='Потребление воды (мл)')
            plt.title('График прогресса потребления')
            plt.ylabel('Ед.измерения')
            plt.xlabel('Прием пищи/воды')
            plt.legend()
            plt.savefig('plot1.png')
            ph = FSInputFile('plot1.png')
            await message.answer_photo(photo=ph)
            plt.clf()
    else:
        await message.reply("Для отслеживания прогресса заполните профиль.\nВведите /set_profile")

# сброс данных о воде и калориях
@router.message(Command("restart_progress"))
async def cmd_restart(message: Message):
    chat_id = message.chat.id
    if chat_id in users.keys():
        users[chat_id]['progress_calories'] = [0]
        users[chat_id]['progress_water'] = [0]
        users[chat_id]['burned_calories'] = 0
        await message.reply("Прогресс по калориям и воде сброшен")
    else:
        await message.reply("Для логирования еды и воды заполните профиль.\nВведите /set_profile")