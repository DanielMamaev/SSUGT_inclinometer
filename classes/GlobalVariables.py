from datetime import timedelta
import copy

class GlobalVariables:
    _time_static = 0
    _indicator_value = None
    _comment_value = None
    _params_vim: dict = {}
    _params_laser: dict = {}
    _flag_time_point = False
    _postprocessing_mode = 0
    _roi_coords = ((0,0), (0,0))
    _params_draw: dict = {}
    _params_control: dict = {}

    @classmethod
    def set_indicator_value(cls, value):
        cls._indicator_value = value

    @classmethod
    def get_indicator_value(cls):
        return cls._indicator_value

    @classmethod
    def set_comment_value(cls, value):
        cls._comment_value = value

    @classmethod
    def get_comment_value(cls):
        return cls._comment_value

    @classmethod
    def add_time_static(cls, seconds):
        cls._time_static += seconds

    @classmethod
    def set_time_static(cls, seconds):
        cls._time_static = seconds

    @classmethod
    def get_time_static(cls):
        return cls._time_static

    @classmethod
    def get_str_time_static(cls):
        minutes, seconds = divmod(cls._time_static, 60)
        text_time = f"{minutes:02d}:{seconds:02d}"
        return text_time
    
    @classmethod
    def get_default_params_vim(cls) -> dict:
        params_vim = {
            "method": 0,
            "thresh": 0,
            "maxval": 0,
            "method_find_contour": 0,
            "min_area_filter": 0,
            "points_mode": 0,
            
            "params_roi": {
                "coords": ((0,0), (0, 0)),
                "visible": False,
                "enable": False
            },
        }
        return params_vim
    
    @classmethod
    def set_params_vim(cls, params: dict):
        cls._params_vim = copy.deepcopy(params)

    @classmethod
    def get_params_vim(cls) -> dict:
        return copy.deepcopy(cls._params_vim)
    
    @classmethod
    def get_default_params_laser(cls):
        params_laser = {
            "method": 0,
            "thresh": 0,
            "maxval": 0,
            "method_find_contour": 0,
            "min_area_filter": 0,
            "points_mode": 0
        }
        return params_laser
    
    @classmethod
    def set_params_laser(cls, params: dict):
        cls._params_laser = copy.deepcopy(params)

    @classmethod
    def get_params_laser(cls) -> dict:
        return copy.deepcopy(cls._params_laser)
    
    @classmethod
    def set_flag_time_point(cls, flag: bool):
        cls._flag_time_point = flag 

    @classmethod
    def get_flag_time_point(cls) -> bool:
        return cls._flag_time_point
    
    @classmethod
    def set_postprocessing_mode(cls, mode: int):
        cls._postprocessing_mode = mode 

    @classmethod
    def get_postprocessing_mode(cls) -> int:
        return cls._postprocessing_mode
    
    @classmethod
    def get_params_draw(cls):
        return copy.deepcopy(cls._params_draw)
    
    @classmethod
    def get_default_params_draw(cls):
        params_draw = {
            "is_segmentation": False,
            "is_draw_rectangle": False,
            "is_draw_points": False,
            "count_draw_points": 1,
            "is_draw_start_position": False
        }
        return params_draw
    
    @classmethod
    def set_params_draw(cls, value):
        cls._params_draw = copy.deepcopy(value)


    @classmethod
    def get_params_control(cls):
        return copy.deepcopy(cls._params_control)
    
    @classmethod
    def set_params_control(cls, value):
        cls._params_control = copy.deepcopy(value)
    
    @classmethod
    def get_defalt_params_control(self):
        params_control = {
            "pause": False,
            "stop": False,
            "next": False,
            "n_shot": 1
        }
        return params_control