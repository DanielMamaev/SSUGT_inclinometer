import json
import logging
import multiprocessing
import os
import threading
import time

import numpy as np
from PySide6.QtGui import QIcon

from classes.DevicesController import DevicesController
from classes.GlobalVariables import GlobalVariables
from classes.GlobalController import GlobalController
from classes.consts import ProcessVIM, TypeDevices, ProcessLaser
from classes.coordinate_system_offset import CoordinateSystemOffset
from classes.segmentation_base import SegmentationBase


class ModuleESP32:
    def __init__(self, source: str | None = None, type_device: TypeDevices = TypeDevices.ESP32_VIM):
        self._x = None
        self._y = None
        self._source: None | str = source
        self._is_streaming: bool = False
        self._type_device = type_device
        self.module_parent_conn, self.module_child_conn = multiprocessing.Pipe()
        self.module_parent_sync_conn, self.module_child_sync_conn = multiprocessing.Pipe()
        self.segmentation = SegmentationBase()
        self.esp32_process: multiprocessing.Process | None = None
        self.esp32_process_id = None
        self._esp32_name = ''
        self._points = np.array([])
        self._center_bubbles_px = (0.0,0.0)
        self._fps = 0
        self._frame: np.ndarray = None
        self._frame_original: np.ndarray = None
        self._is_camera = False
        self._thread = threading.Thread(target=self._prepare_send_data)
        self._is_segmentation: bool | None = None
        self._is_draw_rectangle: bool | None = None
        self._is_draw_point: bool | None = None
        self._count_draw_points: int | None = None
        self._is_draw_start_position: bool | None = None

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def is_segmentation(self):
        if self._is_segmentation is None:
            return GlobalController.is_segmentaion_show()
        return self._is_segmentation

    @property
    def is_draw_rectangle(self):
        if self._is_draw_rectangle is None:
            return GlobalController.is_draw_rectangle()
        return self._is_draw_rectangle

    @property
    def is_draw_point(self):
        if self._is_draw_point is None:
            return GlobalController.is_draw_points()
        return self._is_draw_point

    @property
    def count_draw_points(self):
        if self._count_draw_points is None:
            return GlobalController.get_count_draw_points()
        return self._count_draw_points

    @property
    def is_draw_start_position(self):
        if self._is_draw_start_position is None:
            return GlobalController.is_draw_start_position()
        return self._is_draw_start_position

    @is_segmentation.setter
    def is_segmentation(self, is_segmentation):
        self._is_segmentation = is_segmentation

    # @is_draw_rectangle.setter
    # def is_draw_rectangle(self, is_draw_rectangle):
    #     self._is_draw_rectangle = is_draw_rectangle

    @is_draw_point.setter
    def is_draw_point(self, is_draw_point):
        self._is_draw_point = is_draw_point

    @count_draw_points.setter
    def count_draw_points(self, count_draw_points):
        self._count_draw_points = count_draw_points

    @is_draw_start_position.setter
    def is_draw_start_position(self, is_draw_start_position):
        self._is_draw_start_position = is_draw_start_position

    @property
    def frame_original(self) -> np.ndarray:
        return self._frame_original

    @property
    def is_camera(self) -> bool:
        return self._is_camera

    @property
    def points(self) -> list:
        return self._points

    @property
    def center_bubbles_px(self) -> tuple[float, float]:
        return self._center_bubbles_px

    @property
    def esp32_name(self) -> str:
        return self._esp32_name

    @property
    def fps(self) -> int:
        return self._fps

    @property
    def frame(self) -> np.ndarray:
        return self._frame

    @property
    def source(self) -> str:
        return self._source

    @source.setter
    def source(self, source: str):
        self._source = source

    @property
    def is_streaming(self):
        return self._is_streaming

    @is_streaming.setter
    def is_streaming(self, is_streaming):
        self._is_streaming = is_streaming
    
    def get_default_params_draw(self):
        params_draw = {
            "is_segmentation": False,
            "is_draw_rectangle": False,
            "is_draw_points": False,
            "count_draw_points": 1,
            "is_draw_start_position": False
        }
        return params_draw

    def set_source(self, source: str):
        self._source = source

    def clear_source(self):
        self._source = None

    def start_stream(self):
        self._is_streaming = True

        data_api_controller = DevicesController.get_vim_api_class().get_all_data()
        self._thread.start()

        params_default = {
            "params_vim": GlobalVariables.get_default_params_vim(),
            "params_laser": GlobalVariables.get_default_params_laser(),
            "params_draw": self.get_default_params_draw(),
        }

        self.esp32_process = multiprocessing.Process(target=self.processing_vim, args=(
            self.module_child_conn,
            self.module_child_sync_conn,
            self.segmentation,
            data_api_controller,
            self._source,
            self._type_device,
            params_default
            )
        )
        self.esp32_process.start()

    def stop_stream(self):
        self._is_streaming = False
        self.esp32_process.terminate()

    def _prepare_send_data(self):
        params_draw = self.get_default_params_draw()
        params_vim = GlobalVariables.get_default_params_vim()
        params_laser = GlobalVariables.get_default_params_laser()

        while self._is_streaming:
            time.sleep(0.00001)
            # params draw
            new_params_draw = self.get_default_params_draw()
            new_params_draw["is_segmentation"] = self.is_segmentation
            new_params_draw["is_draw_rectangle"] = self.is_draw_rectangle
            new_params_draw["is_draw_points"] = self.is_draw_point
            new_params_draw["count_draw_points"] = self.count_draw_points
            new_params_draw["is_draw_start_position"] = self.is_draw_start_position
            if params_draw != new_params_draw:
                params_draw.update(new_params_draw)
                self.module_parent_conn.send((params_draw, ProcessVIM.DRAW_OPTIONS))
            
            # Params VIM
            new_params_vim = GlobalVariables.get_default_params_vim()
            
            new_params_vim.update(GlobalVariables.get_params_vim())
            if params_vim != new_params_vim:
                params_vim.update(new_params_vim)
                self.module_parent_conn.send((params_vim, ProcessVIM.PARAMS))
            
            # Params Laser
            new_params_laser = GlobalVariables.get_default_params_laser()
            new_params_laser.update(GlobalVariables.get_params_laser())
            if params_laser != new_params_laser:
                params_laser.update(new_params_laser)
                self.module_parent_conn.send((params_laser, ProcessLaser.PARAMS))
                




    def update_data(self):
        if self.module_parent_conn.poll():
            value, type_data = self.module_parent_conn.recv()
            match type_data:
                case ProcessVIM.DATA_FRAME_VIM:
                    self._points, self._center_bubbles_px, self._frame, self._frame_original, self._fps, self._is_camera = value
                    self.module_parent_sync_conn.send('Done')
                case ProcessVIM.DATA_FRAME_LASER:
                    self._frame, self._frame_original, self._fps, self._is_camera, self._x, self._y, self._points = value
                    self.module_parent_sync_conn.send('Done')
                case ProcessVIM.VIDEO_IS_OVER:
                    self.stop_stream()
                case ProcessVIM.PROCESS_ID:
                    self.esp32_process_id = value

    @staticmethod
    def processing_vim(
        conn,
        sync_conn, 
        segmentation: SegmentationBase,
        data_api_controller,
        source,
        type_device: TypeDevices,
        params_default: dict
        ):

        vim_process_id = -1
        DevicesController.get_vim_api_class().set_all_data(data_api_controller)
        DevicesController.get_vim_api_class().check_is_video_capture(source)
        sync_data = "Done"
        
        params_vim = params_default["params_vim"]
        params_laser = params_default["params_laser"]
        params_draw = params_default["params_draw"]


        prev_center_bubble = None
        prev_center_laser = None

        while vim_process_id is not None:
            time.sleep(0.00001)
            if sync_conn.poll(0.00001):
                sync_data = sync_conn.recv()
            if sync_data == "Done":
                frame_original, fps, is_camera = DevicesController.get_vim_api_class().get_frame()
                
                # # Добавлено условие. Если мы получили пустое изображение (=0). Иначе дальше все ломается
                # if len(frame_original) != 0:
                    
                if frame_original is None:
                    conn.send((False, ProcessVIM.VIDEO_IS_OVER))
                    break
                if type_device == TypeDevices.ESP32_VIM:
                    points, frame, center_bubbles_px = segmentation.vim_frame_processing(frame_original, params_vim, params_draw, prev_center_bubble)
                    if len(points) <= 0:
                        conn.send(((points, center_bubbles_px, frame, frame_original, fps, is_camera), ProcessVIM.DATA_FRAME_VIM))
                        continue

                    prev_center_bubble = center_bubbles_px
                    
                    CoordinateSystemOffset.set_temp_start_position(center_bubbles_px[0])
                    points, frame, center_bubbles_px_update = CoordinateSystemOffset.get_new_image_coords(points, frame, center_bubbles_px[0], params_draw["is_draw_start_position"])
                    center_bubbles_px = (center_bubbles_px_update, center_bubbles_px[1])
                    conn.send(((points, center_bubbles_px, frame, frame_original, fps, is_camera), ProcessVIM.DATA_FRAME_VIM))
                
                elif type_device == TypeDevices.ESP32_LASER:
                    frame, x, y, points_contour = segmentation.laser_frame_processing(
                        frame_original,
                        params_laser,
                        params_draw,
                        prev_center_laser
                        )
                    prev_center_laser = (x, y)
                    conn.send(((frame, frame_original, fps, is_camera, x, y, points_contour), ProcessVIM.DATA_FRAME_LASER))

                sync_data = None

            if conn.poll(0.00001):
                value, type_data = conn.recv()
                match type_data:
                    case ProcessVIM.PROCESS_ID:
                        conn.send((ProcessVIM.PROCESS_ID, os.getpid()))
                    case ProcessVIM.API_CONTROLLER_DATA:
                        data_api_controller = value
                        DevicesController.get_vim_api_class().set_all_data(data_api_controller)
                    case ProcessVIM.DRAW_OPTIONS:
                        params_draw = value
                    case ProcessVIM.PARAMS:
                        params_vim = value
                    case ProcessLaser.PARAMS:
                        params_laser = value
                    case ProcessVIM.KILL_PROCESS:
                        return

    def get_esp32_name(self):
        if not DevicesController.get_vim_api_class().get_is_video_capture():
            self._esp32_name = json.loads(DevicesController.get_vim_api_class().get_name().content).get("name", "esp32")
        if self._esp32_name is None:
            self.connection_is_missing(self._esp32_name)
        elif self._esp32_name == '':
            pass
        else:
            self.connection_is_good(self._esp32_name)

    @staticmethod
    def connection_is_missing(esp32_name):
        logging.info(f"Разорвано соединение с ВИМ: {esp32_name}")
        text_status = f"Разорвано соединение с ВИМ: {esp32_name}"
        icon = QIcon(u":/resource/resource/close.png")
        pixmap = icon.pixmap(16, 16)  # Установите размер иконки
        GlobalController.get_label_status_esp_connect().setText(f"{text_status}")
        GlobalController.get_status_esp_icon().setText("")
        GlobalController.get_status_esp_icon().setPixmap(pixmap)

    @staticmethod
    def connection_is_good(esp32_name):
        logging.info(f"Успешное соединение с ВИМ: {esp32_name}")
        text_status = f"Успешное соединение с ВИМ: {esp32_name}"
        icon = QIcon(u":/resource/resource/check.png")
        pixmap = icon.pixmap(16, 16)  # Установите размер иконки
        GlobalController.get_label_status_esp_connect().setText(f"{text_status}")
        GlobalController.get_status_esp_icon().setText("")
        GlobalController.get_status_esp_icon().setPixmap(pixmap)
