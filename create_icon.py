from PIL import Image, ImageDraw, ImageFont

def draw_wiki_logo(draw, center_x, center_y, size):
    """Рисует белую букву W (логотип Wiki) в указанной области."""
    # Пытаемся использовать шрифт для лучшего отображения
    try:
        # Пробуем загрузить системный шрифт
        # Размер шрифта составляет примерно 65% от размера иконки
        font_size = int(size * 0.65)
        try:
            # Пытаемся использовать системный шрифт (Windows)
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                # Альтернативный шрифт
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
            except:
                # Если не получается загрузить шрифт, используем шрифт по умолчанию
                font = ImageFont.load_default()
        
        # Рисуем букву W
        text = "W"
        # Получаем размер текста для центрирования
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Координаты для центрирования текста
        text_x = center_x - text_width // 2
        text_y = center_y - text_height // 2
        
        # Рисуем белую букву W
        draw.text((text_x, text_y), text, fill=(255, 255, 255), font=font)
        
    except Exception:
        # Если не получается использовать шрифт, рисуем простую геометрическую форму W
        # Вычисляем размеры буквы W
        logo_height = int(size * 0.55)
        logo_width = int(size * 0.6)
        
        x_left = center_x - logo_width // 2
        x_right = center_x + logo_width // 2
        y_top = center_y - logo_height // 2
        y_bottom = center_y + logo_height // 2
        
        # Позиции внутренних углов (где буква разветвляется)
        x_inner_left = center_x - logo_width // 3
        x_inner_right = center_x + logo_width // 3
        
        # Толщина буквы
        stroke = max(3, int(size * 0.08))
        
        # Рисуем W как толстую букву, используя простую форму
        # Создаем контур с учетом толщины
        w_points = [
            # Левая сторона (верх -> низ)
            (x_left - stroke, y_top),
            (x_left - stroke, y_bottom),
            # Переход к левому внутреннему углу
            (x_inner_left - stroke // 2, y_bottom),
            (x_inner_left, y_bottom),
            # Подъем к центральной верхней точке
            (center_x, y_top),
            # Спуск к правому внутреннему углу
            (x_inner_right, y_bottom),
            (x_inner_right + stroke // 2, y_bottom),
            # Правая сторона (низ -> верх)
            (x_right + stroke, y_bottom),
            (x_right + stroke, y_top),
            # Замыкаем через внутреннюю часть
            (x_right - stroke, y_top),
            (x_inner_right + stroke, y_bottom - stroke),
            (center_x, y_top + stroke),
            (x_inner_left - stroke, y_bottom - stroke),
            (x_left + stroke, y_top),
        ]
        
        # Рисуем контур и заливаем
        draw.polygon(w_points, fill=(255, 255, 255))

def draw_icon(size):
    """Рисует логотип Telegram (синий круг) с логотипом Wiki (белая буква W) внутри."""
    # Создаем RGB изображение с прозрачным фоном (будет залит синим кругом)
    img = Image.new("RGB", (size, size), (0, 0, 0))  # Черный фон (будет закрыт кругом)
    draw = ImageDraw.Draw(img)
    
    # Вычисляем размеры с отступами (5% от размера с каждой стороны)
    padding = int(size * 0.05)
    circle_size = size - (padding * 2)
    
    # Координаты для круга (центрированный)
    center_x = size // 2
    center_y = size // 2
    radius = circle_size // 2
    
    # Рисуем синий круг (цвет Telegram)
    circle_coords = [
        center_x - radius,
        center_y - radius,
        center_x + radius,
        center_y + radius
    ]
    
    # Синий цвет Telegram (примерно RGB: 37, 150, 190)
    telegram_blue = (37, 150, 190)
    draw.ellipse(circle_coords, fill=telegram_blue)
    
    # Рисуем белую букву W (логотип Wiki) внутри круга
    draw_wiki_logo(draw, center_x, center_y, size)
    
    return img

# Размеры иконки
sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
icons = [draw_icon(s) for s, _ in sizes]

# Изображения уже в RGB режиме, просто убеждаемся
rgb_icons = []
for icon in icons:
    # Убеждаемся, что изображение в RGB режиме (не палитра)
    if icon.mode != "RGB":
        rgb_img = icon.convert("RGB")
    else:
        rgb_img = icon
    rgb_icons.append(rgb_img)

# Сохранение с явным указанием формата и цветов
# ВАЖНО: Изображения уже в RGB режиме с синим фоном, что гарантирует
# сохранение цветов и избегает автоматической конвертации в градации серого
try:
    rgb_icons[0].save(
        "app.ico",
        format="ICO",
        sizes=sizes,
        append_images=rgb_icons[1:]
    )
    print("✅ Иконка 'app.ico' создана!")
    print("   Дизайн: логотип Telegram (синий круг) с логотипом Wiki (белая буква W)")
    print("   Цвета: синий фон (Telegram Blue), белая буква W")
except Exception as e:
    print(f"❌ Ошибка при сохранении: {e}")
    # Альтернативный способ - сохранить каждое изображение отдельно
    print("Попытка альтернативного метода сохранения...")
    rgb_icons[0].save("app.ico", format="ICO")
    print("✅ Иконка 'app.ico' создана (только один размер)")