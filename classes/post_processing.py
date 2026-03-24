import sys
import time
from datetime import datetime

import cv2

from classes.coordinate_system_offset import CoordinateSystemOffset
from classes.segmentation_base import SegmentationBase
from classes.value_saver import FileSaver
from classes.GlobalVariables import GlobalVariables
from classes.GlobalController import GlobalController
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

    count_shot = 0

    params_control = GlobalVariables.get_defalt_params_control()
    while True:
        
        params_control.update(GlobalVariables.get_params_control())
        if params_control["stop"]:
            break
        elif params_control["next"] and params_control["pause"]:
            count_shot += 1
            if count_shot > params_control["n_shot"]:
                params_control["next"] = False
                count_shot = 0
                GlobalVariables.set_params_control(params_control)
        elif params_control["pause"]:
            time.sleep(0.0000000001)
            continue
        

        # Чтение кадра из видео
        time_2 = time.time()
        ok, frame = video.read()

        # Если кадр не может быть прочитан, то видео закончилось
        if not ok:
            break
        center_bubbles_px = None
        points = None
        x_laser, y_laser = None, None

        params_draw = GlobalVariables.get_default_params_draw()
        params_draw["is_segmentation"] = GlobalController.is_segmentaion_show()
        params_draw["is_draw_rectangle"] = GlobalController.is_draw_rectangle()
        params_draw["is_draw_points"] = GlobalController.is_draw_points()
        params_draw["count_draw_points"] = GlobalController.get_count_draw_points()
        params_draw["is_draw_start_position"] = GlobalController.is_draw_start_position()
        
        match GlobalVariables.get_postprocessing_mode():
            case 0:
                points, image_vim, center_bubbles_px = segmentation.vim_frame_processing(
                    frame,
                    GlobalVariables.get_params_vim(),
                    params_draw
                )
                if param.get("offset", None):
                    if len(points) != 0:
                        points, image_vim, center_bubbles_px_offset_X = CoordinateSystemOffset.get_new_image_coords(
                            points,
                            image_vim,
                            center_bubbles_px[0],
                            params_draw["is_draw_start_position"],
                            param["offset"]
                        )
                        center_bubbles_px = (center_bubbles_px_offset_X, center_bubbles_px[1])
                
                param["signal_send_frame_graphics_view_vim"].emit(image_vim)
                param["label_vim_xy"].setText(f"ВИМ: X={center_bubbles_px[0]}, Y={center_bubbles_px[1]}пикс.")
            
            case 1:
                image_laser, x_laser, y_laser, points = segmentation.laser_frame_processing(
                    frame,
                    GlobalVariables.get_params_laser(),
                    params_draw
                )
                param["signal_send_frame_graphics_view_laser"].emit(image_laser)
                param["label_laser_xy"].setText(f"Laser (x, y): ({x_laser}, {y_laser}) пикс.")
                    
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
                
                method_vim = index_name_method[GlobalVariables.get_params_vim()["method"]]
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
                method_laser = index_name_method[GlobalVariables.get_params_laser()["method"]]

                file_saver.write_data(
                    [
                        formatted_time,
                        x_laser, y_laser, laser_points_x, laser_points_y, laser_points_brig, method_laser, param.get("comment", "")
                    ]
                )

        
        time_sec_sum += time.time() - time_2

    GlobalVariables.set_params_control(GlobalVariables.get_defalt_params_control())

    print(f"Время заняло = {time.time() - time_1} секунд")

    # Освобождение ресурсов
    video.release()
    signal_progressbar.emit(400)
