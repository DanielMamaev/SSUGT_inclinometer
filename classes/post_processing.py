import sys
import time
from datetime import datetime

import cv2

from classes.coordinate_system_offset import CoordinateSystemOffset
from classes.segmentation_base import SegmentationBase
from classes.value_saver import FileSaver
from classes.GlobalVariables import GlobalVariables
from scripts import get_new_points

segmentation = SegmentationBase()

def start_processing(file_path, signal_progressbar, signal_time_label, param: dict = {}):

    # Установка имени видеофайла
    video_input_file_name = file_path


    # Создание объекта для чтения видео
    try:
        video = cv2.VideoCapture(video_input_file_name)
    except:
        signal_progressbar.emit(400)
        return
    total_frames = video.get(cv2.CAP_PROP_FRAME_COUNT)
    file_saver = FileSaver()

    # Проверка на успешное открытие видеофайла
    if not video.isOpened():
        print("Could not open video")
        signal_progressbar.emit(400)
        sys.exit()

    time_1 = time.time()
    is_first_frame = False

    current_frame = 0
    time_sec_sum = 0

    while True:
        # Чтение кадра из видео
        time_2 = time.time()
        ok, frame = video.read()

        # Если кадр не может быть прочитан, то видео закончилось
        if not ok:
            break
        center_bubbles_px = None
        points = None
        x_laser, y_laser = None, None
        
        match GlobalVariables.get_postprocessing_mode():
            case 0:
                points, image, center_bubbles_px = segmentation.vim_frame_processing(frame, param=GlobalVariables.get_param_vim())
                if param.get("offset", None):
                    offset = CoordinateSystemOffset.get_start_position()
                    CoordinateSystemOffset.apply_start_position(param["offset"])
                    if len(points) != 0:
                        points, image, center_bubbles_px_offset_X = CoordinateSystemOffset.get_new_image_coords(points, image, center_bubbles_px[0])
                        center_bubbles_px = (center_bubbles_px_offset_X, center_bubbles_px[1])
                    
                    CoordinateSystemOffset.apply_start_position(offset)
            
            case 1:
                frame, x_laser, y_laser, points = segmentation.laser_frame_processing(frame, param=GlobalVariables.get_param_laser())
                    
                


        current_frame += 1

        remaining_percentage = 100 - ((total_frames - current_frame) / total_frames * 100)
        remaining_time = (time_sec_sum / current_frame) * (total_frames - current_frame)
        signal_time_label.emit(remaining_time)
        # print(f"Оставшееся время: {remaining_time:.2f} секунд")
        time.sleep(0.0000000001)

        # print(f"Оставшиеся кадры: {remaining_percentage:.2f}%")
        signal_progressbar.emit(round(remaining_percentage))

        

        current_time = datetime.now()
        formatted_time = current_time.strftime("%H:%M:%S.%f")
        # if points is not None:
        #     points = points.tolist()
        
        index_name_method = {
            0: "MAX",
            1: "VALEN"
        }
        match GlobalVariables.get_postprocessing_mode():
            case 0:
                if not is_first_frame:
                    file_saver.initialize(
                        headers=[
                            'time',
                            'center_vim_bubble_X', 'center_vim_bubble_Y', 'vim_points_x', 'vim_points_y', "vim_points_brig", 'method_vim',
                            "Comment"
                            ],
                        sep=';')
                    is_first_frame = True

                center_vim_bubble_X, center_vim_bubble_Y = center_bubbles_px
                vim_points_x, vim_points_y, vim_points_brig = get_new_points(points)
                
                method_vim = index_name_method[GlobalVariables.get_param_vim()["method"]]
                file_saver.write_data(
                    [
                        formatted_time,
                        center_vim_bubble_X, center_vim_bubble_Y, vim_points_x, vim_points_y, vim_points_brig, method_vim, param.get("comment", "")
                    ]
                )
            
            case 1:
                if not is_first_frame:
                    file_saver.initialize(
                        headers=[
                            'time',
                            'laser_x', 'laser_y', 'laser_points_x', 'laser_points_y', "laser_points_brig", 'method_laser',
                            "Comment"
                            ],
                        sep=';')
                    is_first_frame = True

                laser_points_x, laser_points_y, laser_points_brig = get_new_points(points)
                method_laser = index_name_method[GlobalVariables.get_param_laser()["method"]]

                file_saver.write_data(
                    [
                        formatted_time,
                        x_laser, y_laser, laser_points_x, laser_points_y, laser_points_brig, method_laser, param.get("comment", "")
                    ]
                )

        
        time_sec_sum += time.time() - time_2

    print(f"Время заняло = {time.time() - time_1} секунд")

    # Освобождение ресурсов
    video.release()
    signal_progressbar.emit(400)
