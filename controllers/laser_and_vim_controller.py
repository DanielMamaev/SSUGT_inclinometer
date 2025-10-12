import os
import subprocess

import cv2
import threading

import numpy as np
from PySide6.QtCore import QTimer, Signal, QObject, Signal
from PySide6.QtWidgets import QMainWindow, QFileDialog


from classes.GlobalController import GlobalController
from classes.GlobalVariables import GlobalVariables
from classes.NivelTool import NivelTool
from classes.ShootingSpeed import ShootingSpeed
from classes.config_controller import ConfigController
from classes.coordinate_system_offset import CoordinateSystemOffset
from classes.stream_controller import StreamController
from controllers import start_menu_controller
from dialogs.dialog_esp32 import Esp32Dialog
from dialogs.dialog_linear_reg import InputDialog
from ui import laser_and_vim
from classes.post_processing import start_processing

class UiVIMLaserController(QMainWindow, laser_and_vim.Ui_MainWindow, QObject):
    signal_send_frame_graphics_view_vim = Signal(np.ndarray)
    signal_send_frame_graphics_view_laser = Signal(np.ndarray)

    signal_progressbar = Signal(int)
    signal_time_label = Signal(float)

    def __init__(self):
        super(UiVIMLaserController, self).__init__()
        self.segmentation: StreamController | None = None

        self.path_param_vim = "data/vim_param.json"
        self.path_param_laser = "data/laser_param.json"
        self.method_find_contour = {
            0: "shape",
            1: "large_obj"
        }
        self.points_mode = {
            0: "contour",
            1: "all"
        }

    def setupUi(self, MainWindow):
        self.MainWindow = MainWindow
        super().setupUi(MainWindow)

        self.set_params_ui()

        self.disable_mode_static()
        self.initialize_global_controller()
        self.timer = QTimer()
        self.timer.timeout.connect(self.onTimeout)
        self.segmentation = None
        self.lineEdit_speed_frame.textChanged.connect(self.speed_frame_line_edit_changed)

        self.add_functions()
        self.lineEdit_source_video.setEnabled(True)
        self.lineEdit_source_video_laser.setEnabled(True)
        self.signal_send_frame_graphics_view_vim.connect(self.send_frame_in_graphics_view_vim)
        self.signal_send_frame_graphics_view_laser.connect(self.send_frame_in_graphics_view_laser)
        self.speed_frame_line_edit_changed()
        self.comboBox_speed_frame.currentIndexChanged.connect(self.combobox_speed_frame_changed)

        self.add_buttons()
        self.add_comboBox()

        self.add_postprocessing()

    # ====== POSTPROCESSING ======
    def add_postprocessing(self):
        self.signal_progressbar.connect(self.set_value_progress_bar)
        self.signal_time_label.connect(self.set_time_label)
        self.save_path = ""
        self.progressBar.setVisible(False)
        self.label_time.setVisible(False)

        self.pushButton_select_path.clicked.connect(lambda: self.get_save_path())
        self.pushButton_start_processing.clicked.connect(self.start_processing)
        self.action_main_window.triggered.connect(self.open_start_window)

        self.comboBox_postprocessing_mode.currentIndexChanged.connect(lambda: GlobalVariables.set_postprocessing_mode(self.comboBox_postprocessing_mode.currentIndex()))
        # self.add_functions()
    
    def set_value_progress_bar(self, percent: int):
        if percent == 400:
            self.progressBar.setVisible(False)
            self.label_time.setVisible(False)
        else:
            self.progressBar.setValue(percent)
    
    def set_time_label(self, seconds: float):
        minutes, seconds = divmod(seconds, 60)
        if minutes > 0:
            self.label_time.setText(f"Осталось {round(minutes)} мин {round(seconds)} с")
        else:
            self.label_time.setText(f"Осталось {round(seconds)} с")
    
    def get_save_path(self):
        """
        Вставка пути где будет создан новый проект
        """

        self.save_path, _ = QFileDialog.getOpenFileNames(None, "Открытие видеофайла", str(os.getcwd()),
                                                         "Все файлы (*.*)")
        if len(self.save_path) == 0:
            self.save_path = ""
            return
        self.save_path = self.save_path[0]

        self.lineEdit.setText(str(self.save_path))
    
    def start_processing(self):
        if not os.path.exists(self.save_path):
            return
        self.progressBar.setVisible(True)
        self.label_time.setVisible(True)
        
        param = {
            "comment": self.lineEdit_postprocessing_comment.text()
        }
        
        offset = int(self.lineEdit_postprocessing_offset.text())
        if offset != 0:
            param["offset"] = offset
        
        t = threading.Thread(target=start_processing, args=(self.save_path, self.signal_progressbar, self.signal_time_label, param))
        t.start()
    # ====== ======
        

    def set_params_ui(self):
        conf_vim = ConfigController(self.path_param_vim)
        param_vim: dict = conf_vim.load()
        
        conf_laser = ConfigController(self.path_param_laser)
        param_laser: dict = conf_laser.load()

        if param_vim != {}:
            self.comboBox_detect_method_vim.setCurrentIndex(param_vim["method"])
            self.lineEdit_thresh_vim.setText(str(param_vim["thresh"]))
            self.lineEdit_maxval_vim.setText(str(param_vim["maxval"]))
            self.comboBox_method_find_contour_vim.setCurrentIndex(param_vim["method_find_contour"])
            self.lineEdit_min_area_figure_vim.setText(str(param_vim["min_area_filter"]))
            self.comboBox_points_mode_vim.setCurrentIndex(param_vim["points_mode"])

            param_vim["method_find_contour"] = self.method_find_contour[param_vim["method_find_contour"]]
            param_vim["points_mode"] = self.points_mode[param_vim["points_mode"]]
            GlobalVariables.set_param_vim(param_vim)
        else:
            self.save_param() # Первый запуск программы

        if param_laser != {}:
            self.comboBox_detect_method_laser.setCurrentIndex(param_laser["method"])
            self.lineEdit_thresh_laser.setText(str(param_laser["thresh"]))
            self.lineEdit_maxval_laser.setText(str(param_laser["maxval"]))
            self.comboBox_method_find_contour_laser.setCurrentIndex(param_laser["method_find_contour"])
            self.lineEdit_min_area_figure_laser.setText(str(param_laser["min_area_filter"]))
            self.comboBox_points_mode_laser.setCurrentIndex(param_laser["points_mode"])

            param_laser["method_find_contour"] = self.method_find_contour[param_laser["method_find_contour"]]
            param_laser["points_mode"] = self.points_mode[param_laser["points_mode"]]
            GlobalVariables.set_param_laser(param_laser)
        else:
            self.save_param() # Первый запуск программы
        
    def add_buttons(self):
        self.pushButton_save_settings.clicked.connect(self.save_param)
    
    def add_comboBox(self):
        self.on_combobox_changed_vim(GlobalVariables.get_param_vim()["method"])
        self.on_combobox_changed_laser(GlobalVariables.get_param_laser()["method"])

        self.comboBox_detect_method_vim.currentIndexChanged.connect(self.on_combobox_changed_vim)
        self.comboBox_detect_method_laser.currentIndexChanged.connect(self.on_combobox_changed_laser)

    def on_combobox_changed_vim(self, index):
        if index == 1:
            self.lineEdit_thresh_vim.setEnabled(True)
            self.lineEdit_maxval_vim.setEnabled(True)
            self.comboBox_method_find_contour_vim.setEnabled(True)
            self.comboBox_points_mode_vim.setEnabled(True)
            self.lineEdit_min_area_figure_vim.setEnabled(True)
            return
        
        self.lineEdit_thresh_vim.setEnabled(False)
        self.lineEdit_maxval_vim.setEnabled(False)
        self.comboBox_method_find_contour_vim.setEnabled(False)
        self.comboBox_points_mode_vim.setEnabled(False)
        self.lineEdit_min_area_figure_vim.setEnabled(False)
    
    def on_combobox_changed_laser(self, index):
        if index == 1:
            self.lineEdit_thresh_laser.setEnabled(True)
            self.lineEdit_maxval_laser.setEnabled(True)
            self.comboBox_method_find_contour_laser.setEnabled(True)
            self.comboBox_points_mode_laser.setEnabled(True)
            self.lineEdit_min_area_figure_laser.setEnabled(True)
            return
        
        self.lineEdit_thresh_laser.setEnabled(False)
        self.lineEdit_maxval_laser.setEnabled(False)
        self.comboBox_method_find_contour_laser.setEnabled(False)
        self.comboBox_points_mode_laser.setEnabled(False)
        self.lineEdit_min_area_figure_laser.setEnabled(False)

    def combobox_speed_frame_changed(self):
        ShootingSpeed.set_mode_speed_frame(self.comboBox_speed_frame.currentIndex())

    def speed_frame_line_edit_changed(self):
        try:
            float(self.lineEdit_speed_frame.text())
        except ValueError:
            self.pushButton_start_stream.setEnabled(False)
        else:
            self.pushButton_start_stream.setEnabled(True)

    def initialize_global_controller(self):
        GlobalController.set_action_static_mode(self.action_static_mode)
        GlobalController.set_label_fps_counter(self.label_fps_counter)
        GlobalController.set_label_vim_temperature(self.label_vim_temp)
        GlobalController.set_label_status_esp_connect(self.label_status_esp_connect)
        GlobalController.set_status_esp_icon(self.label_status_esp_icon)
        GlobalController.set_checkBox_segmentaion_show(self.checkBox_segmentaion_show)
        GlobalController.set_checkBox_view_points(self.checkBox_view_points)
        GlobalController.set_checkBox_enable_record(self.checkBox_enable_record)
        GlobalController.set_checkBox_rectangle_show(self.checkBox_rectangle_show)
        GlobalController.set_spinBox_points(self.spinBox_points)
        GlobalController.set_lineEdit_source_video_vim(self.lineEdit_source_video)
        GlobalController.set_lineEdit_source_video_laser(self.lineEdit_source_video_laser)
        GlobalController.set_checkBox_start_position(self.checkBox_start_position)
        GlobalController.set_push_button_start_stream(self.pushButton_start_stream)
        ShootingSpeed.set_line_edit_speed_frame(self.lineEdit_speed_frame)
        ShootingSpeed.set_combobox_speed_frame(self.comboBox_speed_frame)

    def send_frame_in_graphics_view_vim(self, frame: np.ndarray):
        self.graphicsView_vim.image_cv(frame)

    def send_frame_in_graphics_view_laser(self, frame: np.ndarray):
        self.graphicsView_laser.image_cv(frame)

    def start_timer(self):
        self.timer.start(1000)  # Start the timer with 1 second interval

    def stop_timer(self):
        self.timer.stop()

    def onTimeout(self):
        GlobalVariables.add_time_static(1)
        text_time = GlobalVariables.get_str_time_static()
        self.label_timer.setText(text_time)

    def enable_mode_static(self):
        self.frame_static_1.setVisible(True)
        self.frame_static_2.setVisible(True)

    def disable_mode_static(self):
        self.frame_static_1.setVisible(False)
        self.frame_static_2.setVisible(False)

    def switch_mode_static(self):
        if self.action_static_mode.isChecked():
            self.enable_mode_static()
        else:
            self.disable_mode_static()

    def start_time_point(self):
        self.start_timer()
        GlobalVariables.set_flag_time_point(True)
        self.pushButton_time_point_end.setEnabled(True)
        self.pushButton_time_point_start.setEnabled(False)
        GlobalVariables.set_indicator_value(self.lineEdit_indicator_value.text())
        GlobalVariables.set_comment_value(self.lineEdit_comment_value.text())
        # GlobalVariables.set_indicator_value(False)

    def stop_time_point(self):
        self.stop_timer()
        GlobalVariables.set_flag_time_point(False)
        GlobalVariables.set_time_static(0)
        self.pushButton_time_point_end.setEnabled(False)
        self.pushButton_time_point_start.setEnabled(True)
        # GlobalVariables.set_indicator_value(self.lineEdit_indicator_value.text())
        GlobalVariables.set_indicator_value(None)
        GlobalVariables.set_comment_value(None)

    def update_indicator_value(self):
        pass
        # if self.pushButton_time_point_start.isEnabled():
        #     GlobalVariables.set_indicator_value(self.lineEdit_indicator_value.text())
    
    def update_comment_value(self):
        pass

    def closeEvent(self, event):
        # Здесь можно выполнить необходимые действия перед закрытием
        NivelTool.close_modem()
        self.stop_stream()

    def start_stream(self, cap_vim, cap_laser):
        self.segmentation = StreamController(cap_vim, cap_laser, self.label_value,self.label_laser_xy,
                                             self.signal_send_frame_graphics_view_vim, self.signal_send_frame_graphics_view_laser)
        self.segmentation.start_stream()

    def stop_stream(self):
        if self.segmentation is not None:
            self.segmentation.stop_stream()
        self.graphicsView_vim.scene.clear()
        self.graphicsView_laser.scene.clear()

    def add_functions(self):
        self.pushButton_start_stream.clicked.connect(lambda: self.apply_source())
        self.pushButton_stop_stream.clicked.connect(lambda: self.stop_stream())
        self.pushButton_start_position.clicked.connect(lambda: CoordinateSystemOffset.apply_start_position())
        self.pushButton_time_point_start.clicked.connect(lambda: self.start_time_point())
        self.pushButton_time_point_end.clicked.connect(lambda: self.stop_time_point())
        self.lineEdit_indicator_value.textChanged.connect(self.update_indicator_value)
        self.lineEdit_comment_value.textChanged.connect(self.update_comment_value)

        self.add_actions()

    @staticmethod
    def open_directory():
        path = os.getcwd() + '\\data'
        subprocess.Popen(['explorer', path])

    def add_actions(self):
        NivelTool.set_action_nivel_220(self.menu_Nivel_220)
        NivelTool.set_label_nivel_220(self.label_nivel)
        self.menu_tools.aboutToShow.connect(self.update_list_com_ports)
        self.action_open_directory.triggered.connect(self.open_directory)
        self.action_dialog_regres.triggered.connect(self.open_dialog_parameters_reg)
        self.action_esp32.triggered.connect(self.open_dialog_esp32)
        self.action_static_mode.triggered.connect(self.switch_mode_static)
        self.action_main_window.triggered.connect(lambda: self.open_start_window())

    def open_start_window(self):
        start_menu_window = start_menu_controller.Ui_MainWindow()
        start_menu_window.setupUi(self.MainWindow)

    def open_dialog_esp32(self):
        dialog = Esp32Dialog()
        dialog.exec()

    def open_dialog_parameters_reg(self):
        dialog = InputDialog()
        if dialog.exec():
            print('Данные сохранены')
        else:
            print('Данные отменены')

    def update_list_com_ports(self):
        NivelTool.update_list_com_ports()

    def apply_source(self):
        if self.segmentation is None or not self.segmentation.video_is_started:
            source_video_vim = self.lineEdit_source_video.text()
            source_video_laser = self.lineEdit_source_video_laser.text()
            process = threading.Thread(target=lambda: self.start_stream(source_video_vim, source_video_laser))
            process.start()
    
    # ====== SAVE PARAM VIM and Laser ======
    def save_param(self):
        
        param = {}
        param["method"] = self.comboBox_detect_method_vim.currentIndex()
        param["thresh"] = int(self.lineEdit_thresh_vim.text())
        param["maxval"] = int(self.lineEdit_maxval_vim.text())
        param["method_find_contour"] = self.method_find_contour[self.comboBox_method_find_contour_vim.currentIndex()]
        param["min_area_filter"] = int(self.lineEdit_min_area_figure_vim.text())
        param["points_mode"] = self.points_mode[self.comboBox_points_mode_vim.currentIndex()]

        GlobalVariables.set_param_vim(param)

        conf = ConfigController(self.path_param_vim)
        param["method_find_contour"] = self.comboBox_method_find_contour_vim.currentIndex()
        param["points_mode"] = self.comboBox_points_mode_vim.currentIndex()
        conf.save(param)

      
        param["method"] = self.comboBox_detect_method_laser.currentIndex()
        param["thresh"] = int(self.lineEdit_thresh_laser.text())
        param["maxval"] = int(self.lineEdit_maxval_laser.text())
        param["method_find_contour"] = self.method_find_contour[self.comboBox_method_find_contour_laser.currentIndex()]
        param["min_area_filter"] = int(self.lineEdit_min_area_figure_laser.text())
        param["points_mode"] = self.points_mode[self.comboBox_points_mode_laser.currentIndex()]

        GlobalVariables.set_param_laser(param)

        conf = ConfigController(self.path_param_laser)
        param["method_find_contour"] = self.comboBox_method_find_contour_laser.currentIndex()
        param["points_mode"] = self.comboBox_points_mode_laser.currentIndex()
        conf.save(param)
        