import cv2
import numpy as np

cap = cv2.VideoCapture(r'D:\SSUGT_inclinometer\Valentin\video\laser-2025_10_04 12_58_20 — копия.avi')


# Функция для изменения размера окна
def resize_window(window_name, width, height):
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, width, height)


# Функция для удаления мелких объектов
def remove_small_objects(binary_img, min_area=100):
    """
    Удаляет мелкие шумы и возвращает очищенное бинарное изображение
    """
    # Находим все контуры
    contours, hierarchy = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Создаем маску для "хороших" контуров
    mask = np.zeros_like(binary_img)

    for contour in contours:
        area = cv2.contourArea(contour)
        if area > min_area:  # сохраняем только большие контуры
            cv2.fillPoly(mask, [contour], 255)

    return mask, contours


# Функция для фильтрации контуров по форме и положению
def filter_contours_by_shape(contours, prev_center=None, min_area=1000, max_area=5000,
                             min_aspect_ratio=0.3, max_aspect_ratio=3.0,
                             min_compactness=0.3, max_distance=150):
    """
    Фильтрует контуры по форме, размеру и положению
    """
    if not contours:
        return None, None, None

    valid_contours = []
    contour_info = []

    for contour in contours:
        area = cv2.contourArea(contour)

        # Фильтр по площади
        if area < min_area or area > max_area:
            continue

        # Получаем bounding rectangle для анализа формы
        x, y, w, h = cv2.boundingRect(contour)

        # Фильтр по отношению сторон
        aspect_ratio = w / h if h > 0 else 0
        if aspect_ratio < min_aspect_ratio or aspect_ratio > max_aspect_ratio:
            continue

        # Фильтр по компактности (отношение площади контура к площади bounding box)
        bbox_area = w * h
        compactness = area / bbox_area if bbox_area > 0 else 0
        if compactness < min_compactness:
            continue

        # Вычисляем центр контура
        M = cv2.moments(contour)
        if M["m00"] != 0:
            center_x = int(M["m10"] / M["m00"])
            center_y = int(M["m01"] / M["m00"])
        else:
            center_x = x + w // 2
            center_y = y + h // 2

        valid_contours.append(contour)
        contour_info.append({
            'contour': contour,
            'bbox': (x, y, w, h),
            'center': (center_x, center_y),
            'area': area,
            'aspect_ratio': aspect_ratio,
            'compactness': compactness
        })

    if not valid_contours:
        return None, None, None

    # Выбираем лучший контур
    best_contour = None
    best_score = -1

    for info in contour_info:
        score = 0

        # Предпочтение контурам ближе к предыдущей позиции
        if prev_center is not None:
            distance = np.sqrt((info['center'][0] - prev_center[0]) ** 2 +
                               (info['center'][1] - prev_center[1]) ** 2)
            if distance < max_distance:
                score += (max_distance - distance) / max_distance * 100
            else:
                continue  # Пропускаем слишком далекие контуры
        else:
            # Первый кадр - предпочтение большим контурам
            score = info['area'] / 100

        # Предпочтение контурам с хорошей компактностью
        score += info['compactness'] * 50

        # Предпочтение контурам с нормальным отношением сторон
        if 0.5 <= info['aspect_ratio'] <= 2.0:
            score += 25

        if score > best_score:
            best_score = score
            best_contour = info

    if best_contour is None:
        return None, None, None

    return best_contour['bbox'], best_contour['center'], best_contour['area']


# Функция для получения bounding box и центра объекта (оригинальная)
def get_object_info(contours, min_area=100):
    """
    Возвращает координаты bounding box и центра самого большого объекта
    """
    if not contours:
        return None, None, None

    # Находим контур с максимальной площадью
    largest_contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest_contour)

    if area < min_area:
        return None, None, None

    # Получаем bounding rectangle
    x, y, w, h = cv2.boundingRect(largest_contour)

    # Вычисляем центр объекта
    center_x = x + w // 2
    center_y = y + h // 2

    return (x, y, w, h), (center_x, center_y), area


# Создаем окна
# resize_window('Original Video', 800, 600)
# resize_window('Binary Image', 400, 300)
resize_window('Contours Cleaned', 800, 600)
resize_window('Tracking', 800, 600)

# Переменные для отслеживания
prev_center = None
trajectory = []
use_shape_filter = False  # Переключатель между методами
object_lost_count = 0

print("Управление:")
print("q - выход")
print("c - очистить траекторию")
print("s - сохранить скриншот")
print("f - переключить фильтр (форма/самый большой)")
print("1-4 - изменить минимальную площадь фильтрации")

min_area_filter = 500

while True:
    ret, frame = cap.read()

    if not ret:
        print("Не удалось прочитать кадр или видео закончилось")
        break

    # Создаем копии для отображения
    original_display = frame.copy()
    contours_display = frame.copy()
    tracking_display = frame.copy()
    binary_display = frame.copy()

    # Конвертируем в grayscale и применяем пороговую обработку
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    ret, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

    # Удаляем мелкие объекты и получаем контуры
    cleaned_binary, contours = remove_small_objects(binary, min_area=min_area_filter)

    # Получаем информацию об объекте в зависимости от выбранного метода
    if use_shape_filter:
        bbox, center, area = filter_contours_by_shape(
            contours,
            prev_center=prev_center,
            min_area=min_area_filter,
            max_area=5000,
            min_aspect_ratio=0.3,
            max_aspect_ratio=3.0,
            min_compactness=0.3,
            max_distance=150
        )
        method_name = "Shape Filter"
    else:
        bbox, center, area = get_object_info(contours, min_area=min_area_filter)
        method_name = "Largest Object"

    # ОТОБРАЖЕНИЕ 1: Original Video
    # cv2.imshow('Original Video', original_display)

    # ОТОБРАЖЕНИЕ 2: Binary Image
    # Создаем цветное бинарное изображение для лучшей визуализации
    binary_colored = cv2.cvtColor(cleaned_binary, cv2.COLOR_GRAY2BGR)
    cv2.putText(binary_colored, f'Binary (Area > {min_area_filter})', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    # cv2.imshow('Binary Image', binary_colored)

    # ОТОБРАЖЕНИЕ 3: Contours Cleaned
    # Рисуем все контуры разными цветами
    for i, contour in enumerate(contours):
        color = (0, 255, 0)  # Зеленый по умолчанию

        # Если это выбранный контур, рисуем его красным
        if bbox and center:
            M = cv2.moments(contour)
            if M["m00"] != 0:
                contour_center_x = int(M["m10"] / M["m00"])
                contour_center_y = int(M["m01"] / M["m00"])
                if contour_center_x == center[0] and contour_center_y == center[1]:
                    color = (0, 0, 255)  # Красный для выбранного

        

        # ВЫВОД КООРДИНАТ ТОЧЕК ДЕТЕКТИРУЕМОЙ ОБЛАСТИ
        if len(contour) > 0:
            # Получаем bounding rect для этого контура
            x_cnt, y_cnt, w_cnt, h_cnt = cv2.boundingRect(contour)
            area_cnt = cv2.contourArea(contour)

            # Выводим координаты в консоль для каждого значимого контура
            if area_cnt > min_area_filter:
                cv2.drawContours(contours_display, [contour], -1, color, 2)
                print(
                    f"Contour {i}: BBox({x_cnt}, {y_cnt}, {w_cnt}, {h_cnt}), Area: {area_cnt:.1f}, Points: {len(contour)}")

                # ВЫВОД ЗНАЧЕНИЙ ЯРКОСТИ ДЛЯ КАЖДОЙ ТОЧКИ КОНТУРА
                print(f"  Brightness values for contour {i}:")
                for j, point in enumerate(contour):
                    x_pt = point[0][0]
                    y_pt = point[0][1]
                    # Получаем значение яркости из черно-белого изображения
                    brightness = gray[y_pt, x_pt]
                    print(f"    Point {j}: ({x_pt}, {y_pt}) - Brightness: {brightness}")

                # Также выводим среднюю яркость для всего контура
                brightness_values = []
                for point in contour:
                    x_pt = point[0][0]
                    y_pt = point[0][1]
                    brightness_values.append(gray[y_pt, x_pt])

                if brightness_values:
                    avg_brightness = np.mean(brightness_values)
                    max_brightness = np.max(brightness_values)
                    min_brightness = np.min(brightness_values)
                    print(
                        f"  Contour {i} brightness stats: Avg={avg_brightness:.1f}, Min={min_brightness}, Max={max_brightness}")

                # ВЫВОД ВСЕХ ТОЧЕК ВНУТРИ ДЕТЕКТИРУЕМОЙ ОБЛАСТИ (ЗАЛИТИЕ)
                print(f"  All points inside detected area for contour {i}:")
                # Создаем маску для текущего контура
                contour_mask = np.zeros(gray.shape, dtype=np.uint8)
                cv2.fillPoly(contour_mask, [contour], 255)

                # Находим все точки внутри контура
                points_inside = np.where(contour_mask == 255)
                points_count = len(points_inside[0])

                print(f"    Total points inside area: {points_count}")

                # Выводим первые 20 точек для примера (чтобы не засорять вывод)
                #sample_points = min(1500, points_count)
                sample_points = points_count
                for k in range(sample_points):
                    y_pt = points_inside[0][k]
                    x_pt = points_inside[1][k]
                    brightness = gray[y_pt, x_pt]
                    print(f"      Point {k}: ({x_pt}, {y_pt}) - Brightness: {brightness}")

                if points_count > sample_points:
                    print(f"      ... and {points_count - sample_points} more points")

                # Статистика по всем точкам внутри области
                all_brightness_values = []
                for y_pt, x_pt in zip(points_inside[0], points_inside[1]):
                    all_brightness_values.append(gray[y_pt, x_pt])

                if all_brightness_values:
                    avg_all_brightness = np.mean(all_brightness_values)
                    max_all_brightness = np.max(all_brightness_values)
                    min_all_brightness = np.min(all_brightness_values)
                    std_all_brightness = np.std(all_brightness_values)
                    print(
                        f"  All area brightness stats: Avg={avg_all_brightness:.1f}, Min={min_all_brightness}, Max={max_all_brightness}, Std={std_all_brightness:.1f}")
    # Подписываем количество найденных объектов
    cv2.putText(contours_display, f'Objects: {len(contours)} | Method: {method_name}',
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(contours_display, f'Min Area: {min_area_filter}',
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    cv2.imshow('Contours Cleaned', contours_display)

    # ОТОБРАЖЕНИЕ 4: Tracking
    if bbox and center:
        x, y, w, h = bbox
        center_x, center_y = center

        # Рисуем bounding box
        cv2.rectangle(tracking_display, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # Рисуем центр объекта
        cv2.circle(tracking_display, (center_x, center_y), 5, (0, 0, 255), -1)

        # Рисуем перекрестие в центре
        cv2.line(tracking_display, (center_x - 10, center_y),
                 (center_x + 10, center_y), (0, 0, 255), 2)
        cv2.line(tracking_display, (center_x, center_y - 10),
                 (center_x, center_y + 10), (0, 0, 255), 2)

        # Добавляем точку в траекторию
        trajectory.append((center_x, center_y))

        # Рисуем траекторию (последние 50 точек)
        for i in range(1, min(len(trajectory), 50)):
            cv2.line(tracking_display, trajectory[i - 1], trajectory[i], (255, 0, 0), 2)

        # Отображаем координаты и информацию
        info_text = [
            f'Coordinates: X={center_x}, Y={center_y}',
            f'BBox: ({x}, {y}) - ({x + w}, {y + h})',
            f'Size: {w}x{h} pixels | Area: {area:.1f} px',
            f'Method: {method_name} | Objects: {len(contours)}',
            f'Min Area: {min_area_filter} | Tracking: GOOD'
        ]

        # Выводим информацию на изображение
        for i, text in enumerate(info_text):
            color = (0, 255, 0) if i == 4 else (255, 255, 255)
            cv2.putText(tracking_display, text, (10, 30 + i * 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # Выводим координаты в консоль
        print(f"Object detected - Center: ({center_x}, {center_y}), Area: {area:.1f}, Method: {method_name}")

        prev_center = center
        object_lost_count = 0
    else:
        object_lost_count += 1
        # Если объект не найден
        cv2.putText(tracking_display, 'No object detected', (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(tracking_display, f'Method: {method_name} | Min Area: {min_area_filter}',
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        print(f"No object detected - Method: {method_name}, Min Area: {min_area_filter}")

        # Если объект потерян долгое время, сбрасываем предыдущую позицию
        if object_lost_count > 30:
            prev_center = None
            trajectory = []
            print("Tracking reset due to prolonged object loss")

    cv2.imshow('Tracking', tracking_display)

    # Обработка клавиш
    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break
    elif key == ord('c'):
        # Очистка траектории
        trajectory = []
        print("Trajectory cleared")
    elif key == ord('s'):
        # Сохранение текущего кадра
        cv2.imwrite('tracking_screenshot.jpg', tracking_display)
        print("Screenshot saved as 'tracking_screenshot.jpg'")
    elif key == ord('f'):
        # Переключение между методами фильтрации
        use_shape_filter = not use_shape_filter
        method_name = "Shape Filter" if use_shape_filter else "Largest Object"
        print(f"Filter method changed to: {method_name}")
    elif key == ord('1'):
        min_area_filter = 25
        print(f"Min area filter changed to: {min_area_filter}")
    elif key == ord('2'):
        min_area_filter = 50
        print(f"Min area filter changed to: {min_area_filter}")
    elif key == ord('3'):
        min_area_filter = 100
        print(f"Min area filter changed to: {min_area_filter}")
    elif key == ord('4'):
        min_area_filter = 200
        print(f"Min area filter changed to: {min_area_filter}")

cap.release()
cv2.destroyAllWindows()

# Вывод итоговой информации
print(f"\n=== TRACKING SUMMARY ===")
print(f"Total trajectory points: {len(trajectory)}")
print(f"Final filter method: {'Shape Filter' if use_shape_filter else 'Largest Object'}")
print(f"Final min area filter: {min_area_filter}")
if trajectory:
    print(f"First point: {trajectory[0]}")
    print(f"Last point: {trajectory[-1]}")
