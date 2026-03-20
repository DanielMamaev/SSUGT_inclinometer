import time
import cv2
import numpy as np
import logging


class SegmentationBase:
    def __init__(self):
        self.crop_x = 0
        self.crop_y = 0
        self.crop_w = 0
        self.crop_h = 0
        self.area_crop = None

    @staticmethod
    def delete_polygons(image):
        # Находим контуры на бинарном изображении
        contours, _ = cv2.findContours(
            image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Инициализация переменных для хранения максимальной площади и соответствующего контура
        max_area = 0
        max_contour = None

        # Перебор контуров для нахождения самого большого
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > max_area:
                max_area = area
                max_contour = contour

        # Создание копии исходного изображения для вывода результата
        result = image.copy()

        # Закрашивание всех контуров, кроме самого большого, в черный цвет
        for contour in contours:
            if contour is not max_contour:
                cv2.drawContours(result, [contour], 0, 0, -1)
        return result, max_contour

    def get_xywh_crop_from_contour(self, max_contour):
        if self.crop_x == 0:
            self.crop_x, self.crop_y, self.crop_w, self.crop_h = cv2.boundingRect(
                max_contour)
        if self.area_crop is None:
            x, y, w, h = cv2.boundingRect(max_contour)
            self.area_crop = w * h
        x, y, w, h = cv2.boundingRect(max_contour)
        area_crop = w * h
        if min(self.area_crop, area_crop) / max(self.area_crop, area_crop) < 0.8:
            self.crop_x, self.crop_y, self.crop_w, self.crop_h = cv2.boundingRect(
                max_contour)
            self.area_crop = self.crop_w * self.crop_h

        return self.crop_x, self.crop_y, self.crop_w, self.crop_h

    def search_bubble(self, cropped_image, ret_th):
        ret_th, thresh = cv2.threshold(cropped_image, 0, 255, cv2.THRESH_OTSU)
        # ret_th, thresh = cv2.threshold(cropped_image, ret_th, 255, cv2.THRESH_BINARY)
        cv2.imshow('thresh', thresh)
        cv2.waitKey(1)

    def v2_frame_proccesing(self, frame_original):
        frame_original.copy()
        frame = cv2.cvtColor(frame_original, cv2.COLOR_BGR2GRAY)
        frame = cv2.medianBlur(frame, 5)
        ret_th, thresh = cv2.threshold(frame, 0, 255, cv2.THRESH_OTSU)

        thresh, max_contour = self.delete_polygons(thresh)
        x, y, w, h = self.get_xywh_crop_from_contour(max_contour)

        cropped_image = frame[y:y + h, x:x + w]  # обрезка изображения
        self.search_bubble(cropped_image, ret_th)

        return [], thresh, 0

    # ====== LASER PROCESSING ======
    def laser_frame_processing(
            self,
            frame_original: np.ndarray,
            param_laser: dict,
            params_draw: dict,
            prev_center_laser=None
    ):

        # (output_image, min_contour_center_x, min_contour_center_y, points_contour)
        results = None

        match param_laser["method"]:
            case 0:
                results = self.laser_frame_processing_1(frame_original)
            case 1:
                laser_points, frame_result, center_laser = self._vim_frame_processing_method_2(
                    frame_original,
                    param_laser,
                    params_draw,
                    prev_center_laser
                )
                results = (
                    frame_result, center_laser[0], center_laser[1], laser_points)

        return results

    def laser_frame_processing_1(self, frame_original: np.ndarray, is_segmentaion_show: bool = False,
                                 is_draw_rectangle: bool = False,
                                 is_draw_points: bool = False):
        """Метод Максима Попкова"""
        frame_result = frame_original.copy()
        # Извлечение R канала (индекс 2 в BGR)
        red_channel = frame_result[:, :, 2]

        frame_result = red_channel
        frame_result = cv2.medianBlur(frame_result, 5)
        ret_th, thresh = cv2.threshold(frame_result, 0, 255, cv2.THRESH_OTSU)

        # Определение структурного элемента (ядра)
        kernel = np.ones((11, 11), np.uint8)  # 5x5 квадратное ядро

        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        # Найти контуры
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Получаем размеры изображения
        height, width = frame_result.shape

        # Вычисляем центр изображения
        center_x, center_y = width // 2, height // 2

        # Переменные для хранения самого большого контура и его площади
        largest_contour = None
        min_distance = float('inf')
        min_contour_center_x = 0
        min_contour_center_y = 0

        closest_contour_to_center = None

        # Фильтруем контуры
        for contour in contours:
            M = cv2.moments(contour)
            if M["m00"] != 0:  # Избегаем деления на ноль
                contour_center_x = int(M["m10"] / M["m00"])
                contour_center_y = int(M["m01"] / M["m00"])

                # Вычисляем расстояние от центра изображения до центра контура
                distance = np.sqrt((contour_center_x - center_x)
                                   ** 2 + (contour_center_y - center_y) ** 2)

                # Условие для проверки, что контур близок к центру (например, меньше 100 пикселей)
                if distance < min_distance:  # Можете изменить этот порог по своему усмотрению
                    min_distance = distance
                    filtered_contours = [contour]
                    min_contour_center_x = contour_center_x
                    min_contour_center_y = contour_center_y

        # Рисуем отфильтрованные контуры на исходном изображении
        output_image = frame_original
        # Удаляем ось длины 1
        points_contour = np.squeeze(filtered_contours[0], axis=1)
        # thresh = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
        cv2.drawContours(output_image, filtered_contours, -1, (0, 255, 0), 2)

        return output_image, min_contour_center_x, min_contour_center_y, points_contour

    def vim_frame_processing(
            self,
            frame_original: np.ndarray,
            param_vim: dict,
            params_draw: dict,
            prev_center_bubble=None,
    ):

        results = tuple()  # (Массив точек контура, фрейм, центр бабл в пикселях)
        match param_vim["method"]:
            case 0:
                results = self._vim_frame_processing_method_1(
                    frame_original, params_draw)
            case 1:
                results = self._vim_frame_processing_method_2(
                    frame_original,
                    param_vim,
                    params_draw,
                    prev_center_bubble,
                )

        return results

    # ============ METHOD 2 ============

    # Функция для удаления мелких объектов
    @staticmethod
    def _remove_small_objects(binary_img, min_area=100):
        """
        Удаляет мелкие шумы и возвращает очищенное бинарное изображение
        """
        # Находим все контуры
        contours, hierarchy = cv2.findContours(
            binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Создаем маску для "хороших" контуров
        mask = np.zeros_like(binary_img)

        for contour in contours:
            area = cv2.contourArea(contour)
            if area > min_area:  # сохраняем только большие контуры
                cv2.fillPoly(mask, [contour], 255)

        return mask, contours

    # Функция для фильтрации контуров по форме и положению
    @staticmethod
    def _filter_contours_by_shape(
        contours,
        prev_center=None,
        min_area=1000,
        max_area=5000,
        min_aspect_ratio=0.3,
        max_aspect_ratio=3.0,
        min_compactness=0.3,
        max_distance=1600
    ):
        """
        Фильтрует контуры по форме, размеру и положению
        """
        if not contours:
            return (0, 0, 0, 0), (0, 0), 0.0, []

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
            return (0, 0, 0, 0), (0, 0), 0.0, []

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
            return (0, 0, 0, 0), (0, 0), 0.0, []

        return best_contour['bbox'], best_contour['center'], best_contour['area'], best_contour['contour']

    # Функция для получения bounding box и центра объекта (оригинальная)
    @staticmethod
    def _get_object_info(contours, min_area=100):
        """
        Возвращает координаты bounding box и центра самого большого объекта
        """
        if not contours:
            return (0, 0, 0, 0), (0, 0), 0.0, []

        # Находим контур с максимальной площадью
        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)

        if area < min_area:
            return (0, 0, 0, 0), (0, 0), 0.0, []

        # Получаем bounding rectangle
        x, y, w, h = cv2.boundingRect(largest_contour)

        # Вычисляем центр объекта
        center_x = x + w // 2
        center_y = y + h // 2

        return (x, y, w, h), (center_x, center_y), area, largest_contour

    def _vim_frame_processing_method_2(
            self,
            frame_original: np.ndarray,
            param_vim: dict,
            params_draw: dict,
            prev_center_bubble=None
    ):
        """
        Метод разработан Валентином Янгалышевым
        param = {
            "thresh": 180,
            "maxval": 255,
            "method_find_contour": "large_obj" or "shape",
            "min_area_filter": 500,
            "points_mode": "all" or "contour"

        }
        """
        center_bubble = (0, 0)
        bubble_points = np.array([])
        frame_result = frame_original.copy()

        coord_rect = (0, 0, 0, 0)
        area = 0
        largest_contour = np.array([])

        roi_offset_x = 0
        roi_offset_y = 0
        work_frame = frame_result

        if param_vim.get("params_roi", False) and param_vim["params_roi"]["enable"]:
            p1, p2 = param_vim["params_roi"]["coords"]

            x1, y1 = p1
            x2, y2 = p2

            x1, x2 = sorted((x1, x2))
            y1, y2 = sorted((y1, y2))

            h_img, w_img = frame_result.shape[:2]
            x1 = max(0, min(x1, w_img))
            x2 = max(0, min(x2, w_img))
            y1 = max(0, min(y1, h_img))
            y2 = max(0, min(y2, h_img))

            if x2 > x1 and y2 > y1:
                work_frame = frame_result[y1:y2, x1:x2]
                roi_offset_x = x1
                roi_offset_y = y1

        gray = cv2.cvtColor(work_frame, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, param_vim["thresh"], param_vim["maxval"], cv2.THRESH_BINARY)

        cleaned_binary, contours = self._remove_small_objects(binary, min_area=param_vim["min_area_filter"])

        if param_vim["method_find_contour"] == "shape":
            coord_rect, center_bubble, area, largest_contour = self._filter_contours_by_shape(
                contours,
                prev_center=prev_center_bubble,
                min_area=param_vim["min_area_filter"],
                max_area=5000,
                min_aspect_ratio=0.3,
                max_aspect_ratio=3.0,
                min_compactness=0.3,
                max_distance=150
            )
        elif param_vim["method_find_contour"] == "large_obj":
            coord_rect, center_bubble, area, largest_contour = self._get_object_info(contours, min_area=param_vim["min_area_filter"])

        if len(largest_contour) > 0:
            largest_contour = largest_contour.copy()
            largest_contour[:, 0, 0] += roi_offset_x
            largest_contour[:, 0, 1] += roi_offset_y

            x, y, w, h = coord_rect
            coord_rect = (x + roi_offset_x, y + roi_offset_y, w, h)

            center_bubble = (
                center_bubble[0] + roi_offset_x,
                center_bubble[1] + roi_offset_y
            )

        color = (0, 255, 0)

        if len(largest_contour) > 0 and area > param_vim["min_area_filter"]:
            bubble_points_temp = []

            gray_full = cv2.cvtColor(frame_result, cv2.COLOR_BGR2GRAY)

            if param_vim["points_mode"] == "all":
                contour_mask = np.zeros(gray_full.shape, dtype=np.uint8)
                cv2.fillPoly(contour_mask, [largest_contour], 255)
                y_pts, x_pts = np.where(contour_mask == 255)
                brig = gray_full[y_pts, x_pts]
                bubble_points_temp = np.column_stack((x_pts, y_pts, brig))

            elif param_vim["points_mode"] == "contour":
                re_contour = largest_contour.reshape(-1, 2)
                x = re_contour[:, 0]
                y = re_contour[:, 1]
                brig = gray_full[y, x]
                bubble_points_temp = np.column_stack((x, y, brig))

            bubble_points = bubble_points_temp

        if params_draw["is_segmentation"]:
            if roi_offset_x != 0 or roi_offset_y != 0:
                binary_full = np.zeros(frame_result.shape[:2], dtype=np.uint8)
                h_bin, w_bin = cleaned_binary.shape[:2]
                binary_full[roi_offset_y:roi_offset_y + h_bin,
                            roi_offset_x:roi_offset_x + w_bin] = cleaned_binary
                frame_result = cv2.cvtColor(binary_full, cv2.COLOR_GRAY2BGR)
            else:
                frame_result = cv2.cvtColor(cleaned_binary, cv2.COLOR_GRAY2BGR)

        if params_draw["is_draw_points"]:
            for x, y, _ in bubble_points:
                frame_result = cv2.circle(
                    frame_result, (x, y), 2, (255, 0, 0), -1)
                
        if params_draw["is_draw_rectangle"]:
            x, y, w, h = coord_rect
            frame_result = cv2.rectangle(
                frame_result, (x, y), (x + w, y + h), (0, 255, 255), 2)

        if param_vim.get("params_roi", False):
            if param_vim["params_roi"]["visible"]:
                color = (0, 255, 0) if param_vim["params_roi"]["enable"] else (0, 0, 255)
                p1, p2 = param_vim["params_roi"]["coords"]
                frame_result = cv2.rectangle(frame_result, p1, p2, color, 2)

        return bubble_points, frame_result, center_bubble

    def _vim_frame_processing_method_1(
            self,
            frame_original: np.ndarray,
            params_draw: dict
    ):
        """Метод разработан Максимом Попковым"""

        frame_result = frame_original.copy()
        frame = cv2.cvtColor(frame_original, cv2.COLOR_BGR2GRAY)
        ret_th, thresh = cv2.threshold(frame, 0, 255, cv2.THRESH_OTSU)

        # Найти контуры
        cnts = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = cnts[0] if len(cnts) == 2 else cnts[1]

        # Найти самый большой контур (прямоугольник)
        max_area = 0
        max_contour = None

        for c in cnts:
            area = cv2.contourArea(c)
            if area > max_area:
                max_area = area
                max_contour = c

        # Получить ограничивающий прямоугольник
        x, y, w, h = cv2.boundingRect(max_contour)
        # Условие если новый прямоугольник отличается больше, чем на 10 процентов, тогда мы заменяем значения
        try:
            if abs((x - self.crop_x) / (x + self.crop_x)) > 0.1 or abs((y - self.crop_y) / (y + self.crop_y)) > 0.1:
                self.crop_x, self.crop_y, self.crop_w, self.crop_h = x, y, w, h
            x, y, w, h = self.crop_x, self.crop_y, self.crop_w, self.crop_h
        except ZeroDivisionError:
            pass
        except Exception as e:
            print(e)

        cropped = frame[y:y + h, x:x + w]
        mask = thresh[y:y + h, x:x + w]
        cropped[mask == 0] = 255

        if cropped is None or cropped.size == 0:
            print("Ошибка: изображение пустое!")
            return np.array([]), frame_result, (0.0, 0, 0)

        # Применить медианный фильтр с ядром размером 3x3
        cropped = cv2.medianBlur(cropped, 5)

        ret_th, thresh = cv2.threshold(cropped, 0, 255, cv2.THRESH_OTSU)

        # Найти контуры
        cnts = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        cnts = cnts[0] if len(cnts) == 2 else cnts[1]

        # Найти самый большой контур (прямоугольник)
        area_list = []

        for c in cnts:
            area = cv2.contourArea(c)
            if len(area_list) == 0 or area > area_list[-1][0]:
                area_list.append([area, c])

        height_t, width_t = thresh.shape[:2]
        sorted_area_list = sorted(area_list, key=lambda x: x[0])
        index_delete_later = []
        for i in range(len(sorted_area_list)):
            if sorted_area_list[i][0] > (height_t * width_t) * 0.15:
                index_delete_later.append(i)
            for j in range(len(sorted_area_list[i][1])):
                if abs(sorted_area_list[i][1][j][0][0] - width_t) / width_t < 0.01 or abs(
                        sorted_area_list[i][1][j][0][0] - width_t) / width_t > 0.99:
                    index_delete_later.append(i)
                    break
                if abs(sorted_area_list[i][1][j][0][1] - height_t) / height_t < 0.05 or abs(
                        sorted_area_list[i][1][j][0][1] - height_t) / height_t > 0.95:
                    index_delete_later.append(i)
                    break
        temp_sorted_list = []
        for i in range(len(sorted_area_list)):
            if not i in index_delete_later:
                temp_sorted_list.append(sorted_area_list[i])
        sorted_area_list = temp_sorted_list

        try:
            x, y, w, h = cv2.boundingRect(sorted_area_list[-1][1])
            if len(sorted_area_list) < 3:
                x, y, w, h = cv2.boundingRect(sorted_area_list[-1][1])

        except IndexError:
            try:
                x, y, w, h = cv2.boundingRect(sorted_area_list[-1][1])
            except IndexError:
                print(IndexError)
                return np.array([]), frame_original, (0, 0)
        cv2.rectangle(cropped, (x, y), (x + w, y + h), (0, 0, 0), 1)
        # Создание графика с точками
        # Транспонирование массива
        cv2.drawContours(cropped, sorted_area_list[-1][1], -1, (0, 255, 0), 2)
        xy_array = sorted_area_list[-1][1]

        transposed_array = np.transpose(xy_array)

        # Разделение транспонированного массива на два массива
        split_array = np.split(transposed_array, 2)

        # Преобразование каждого массива в одномерный
        x_array: np.array = split_array[0].flatten()
        y_array: np.array = split_array[1].flatten()

        x_2, y_2, w_2, h_2 = self.crop_x, self.crop_y, self.crop_w, self.crop_h

        x_array += x_2
        y_array += y_2

        merged_array = np.hstack(
            (x_array.reshape(-1, 1), y_array.reshape(-1, 1)))
        # Получаем индексы отсортированных значений x
        sorted_indices = np.argsort(merged_array[:, 0])

        # Сортируем merged_array по значениям x
        sorted_merged_array = merged_array[sorted_indices]

        x, y, w, h = x + x_2, y + y_2, w, h
        new_frame = None
        if params_draw["is_segmentation"]:
            new_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        if params_draw["is_draw_rectangle"]:
            if new_frame is None:
                new_frame = cv2.rectangle(
                    frame_original, (x, y), (x + w, y + h), (0, 255, 0), 5)
            else:
                new_frame = cv2.rectangle(
                    new_frame, (x, y), (x + w, y + h), (0, 255, 0), 5)
        if params_draw["is_draw_points"]:
            if new_frame is None:
                new_frame = frame_original

            for i in range(0, x_array.shape[0], params_draw["count_draw_points"]):
                x_cir = x_array[i]
                y_cir = y_array[i]
                radius = 5
                color = (255, 0, 0)
                thickness = 2
                new_frame = cv2.circle(
                    new_frame, (x_cir, y_cir), radius, color, thickness)
        if new_frame is not None:
            frame_result = new_frame

        center_bubbles_px = (((x + (x + w)) / 2), ((y + (y + h)) / 2))

        return sorted_merged_array, frame_result, center_bubbles_px

    def frame_processing(self, frame_original, draw_rect=False, draw_segm=False):
        frame_result = frame_original.copy()
        frame = cv2.cvtColor(frame_original, cv2.COLOR_BGR2GRAY)
        ret_th, thresh = cv2.threshold(frame, 0, 255, cv2.THRESH_OTSU)

        # Найти контуры
        cnts = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = cnts[0] if len(cnts) == 2 else cnts[1]

        # Найти самый большой контур (прямоугольник)
        max_area = 0
        max_contour = None

        for c in cnts:
            area = cv2.contourArea(c)
            if area > max_area:
                max_area = area
                max_contour = c

        # Получить ограничивающий прямоугольник
        x, y, w, h = cv2.boundingRect(max_contour)
        # Условие если новый прямоугольник отличается больше, чем на 10 процентов, тогда мы заменяем значения
        if abs((x - self.crop_x) / (x + self.crop_x)) > 0.1 or abs((y - self.crop_y) / (y + self.crop_y)) > 0.1:
            self.crop_x, self.crop_y, self.crop_w, self.crop_h = x, y, w, h

        x, y, w, h = self.crop_x, self.crop_y, self.crop_w, self.crop_h
        cropped = frame[y:y + h, x:x + w]
        mask = thresh[y:y + h, x:x + w]
        # mask = cv2.bitwise_not(mask)
        cropped[mask == 0] = 255

        # frame_copy = frame.copy()

        # cv2.imshow("frame", frame)
        # Применить медианный фильтр с ядром размером 3x3
        cropped = cv2.medianBlur(cropped, 5)

        ret_th, thresh = cv2.threshold(cropped, 0, 255, cv2.THRESH_OTSU)

        # Найти контуры
        cnts = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        cnts = cnts[0] if len(cnts) == 2 else cnts[1]
        # thresh = cv2.medianBlur(thresh, 5)

        # Найти самый большой контур (прямоугольник)
        max_area = 0
        max_area_2 = 0
        max_contour = None
        area_list = []

        for c in cnts:
            area = cv2.contourArea(c)
            if len(area_list) == 0 or area > area_list[-1][0]:
                # max_area = area
                # max_contour = c
                area_list.append([area, c])

        sorted_area_list = sorted(area_list, key=lambda x: x[0])
        try:
            x, y, w, h = cv2.boundingRect(sorted_area_list[-3][1])
            if len(sorted_area_list) < 3:
                x, y, w, h = cv2.boundingRect(sorted_area_list[-2][1])

        except IndexError:
            x, y, w, h = cv2.boundingRect(sorted_area_list[0][1])
        cv2.rectangle(cropped, (x, y), (x + w, y + h), (0, 0, 0), 1)
        # x, y, w, h = cv2.boundingRect(sorted_area_list[-3][1])
        # cv2.rectangle(cropped, (x, y), (x + w, y + h), (0, 0, 0), 2)
        # Создание графика с точками
        # Транспонирование массива
        cv2.drawContours(cropped, sorted_area_list[-3][1], -1, (0, 255, 0), 2)
        xy_array = sorted_area_list[-3][1]

        condition = xy_array[1] < 65

        # находим индексы элементов, которые соответствуют условию
        indices = np.where(condition)[0]

        # удаляем элементы из массива A по найденным индексам
        # xy_array = np.delete(xy_array, indices)
        # new_xy_array = np.array([])
        # for xy in xy_array:
        #     if xy[0][1] > 65:
        #         new_xy_array = np.append(new_xy_array, xy[0])
        # # print(new_xy_array)
        # xy_array = new_xy_array

        # xy_array = np.where(xy_array[1] < 65, xy_array, xy_array )
        reshaped_data = xy_array.reshape(-1, xy_array.shape[-1])
        # np.savetxt('data.csv', reshaped_data, delimiter=',')
        transposed_array = np.transpose(xy_array)

        # Разделение транспонированного массива на два массива
        split_array = np.split(transposed_array, 2)

        # Преобразование каждого массива в одномерный
        x_array: np.array = split_array[0].flatten()
        y_array: np.array = split_array[1].flatten()
        # plt.scatter(x_array, y_array)
        # plt.xlabel('X')  # подпись оси x
        # plt.ylabel('Y')  # подпись оси y
        # plt.title('Scatter Plot')  # заголовок графика
        # plt.grid(True)  # включение сетки
        # plt.show()  # вывод графика

        # cv2.imshow("frame_copy", cropped)
        # cv2.imshow("frame2", thresh)
        # Обрезка каждого канала отдельно
        x_2, y_2, w_2, h_2 = self.crop_x, self.crop_y, self.crop_w, self.crop_h
        # cropped_blue = frame_original[y_2:y_2 + h_2, x_2:x_2 + w_2, 0]  # Blue channel
        # cropped_green = frame_original[y_2:y_2 + h_2, x_2:x_2 + w_2, 1]  # Green channel
        # cropped_red = frame_original[y_2:y_2 + h_2, x_2:x_2 + w_2, 2]  # Red channel
        #
        # # Объединение каналов в цветное изображение
        # cropped_color = cv2.merge([cropped_blue, cropped_green, cropped_red])
        x, y, w, h = x + x_2, y + y_2, w, h
        if draw_rect and draw_segm:
            frame_result = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            frame_result = cv2.rectangle(
                frame_result.copy(), (x, y), (x + w, y + h), (0, 255, 0), 5)
        elif draw_rect:
            frame_result = cv2.rectangle(
                frame_original.copy(), (x, y), (x + w, y + h), (0, 255, 0), 5)
        elif draw_segm:
            frame_result = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

        center_bubbles_px = abs(x - (x + w)) / 2

        return x_array, y_array, frame_result, center_bubbles_px


if __name__ == "__main__":
    segm = SegmentationBase()

    vid = cv2.VideoCapture(
        r"D:\SSUGT_inclinometer\Valentin\video\laser-2025_10_04 12_58_20 — копия.avi")

    while True:
        ret, frame = vid.read()
        if not ret:
            print("Видео закончено или не читается.")
            break

        param = {
            "thresh": 180,
            "maxval": 255,
            "method_filter": "large_obj",
            "min_area_filter": 500,
            "points_mode": "all"

        }
        bubbles_points, frame_upd, center_bubble = segm.vim_frame_processing(
            frame, method=2, param=param, is_segmentaion_show=True, is_draw_points=True)
        print(len(bubbles_points), center_bubble)
        cv2.imshow("Frame", frame_upd)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        time.sleep(0.05)
    vid.release()
    cv2.destroyAllWindows()
