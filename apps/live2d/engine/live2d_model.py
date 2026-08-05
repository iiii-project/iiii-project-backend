import json

import chardet
from loguru import logger


class Live2dModel:
    """Prepares and stores Live2D model info/emotion-map. Does not talk to the network."""

    def __init__(self, live2d_model_name: str, model_dict_path: str = "model_dict.json"):
        self.model_dict_path = model_dict_path
        self.live2d_model_name = live2d_model_name
        self.set_model(live2d_model_name)

    def set_model(self, model_name: str) -> None:
        self.model_info = self._lookup_model_info(model_name)
        self.emo_map = {k.lower(): v for k, v in self.model_info["emotionMap"].items()}
        self.emo_str = " ".join([f"[{key}]," for key in self.emo_map.keys()])

    def _load_file_content(self, file_path: str) -> str:
        for encoding in ("utf-8", "utf-8-sig", "gbk", "gb2312", "ascii"):
            try:
                with open(file_path, "r", encoding=encoding) as file:
                    return file.read()
            except UnicodeDecodeError:
                continue

        with open(file_path, "rb") as file:
            raw_data = file.read()
        detected_encoding = chardet.detect(raw_data)["encoding"]
        if detected_encoding:
            try:
                return raw_data.decode(detected_encoding)
            except UnicodeDecodeError:
                pass
        raise UnicodeError(f"Failed to decode {file_path} with any encoding")

    def _lookup_model_info(self, model_name: str) -> dict:
        self.live2d_model_name = model_name
        file_content = self._load_file_content(self.model_dict_path)
        model_dict = json.loads(file_content)

        matched_model = next((m for m in model_dict if m["name"] == model_name), None)
        if matched_model is None:
            logger.critical(f"Unable to find {model_name} in {self.model_dict_path}.")
            raise KeyError(f"{model_name} not found in model dictionary {self.model_dict_path}.")

        logger.info("Model Information Loaded.")
        return matched_model

    def extract_emotion(self, str_to_check: str) -> list:
        expression_list = []
        str_to_check = str_to_check.lower()

        i = 0
        while i < len(str_to_check):
            if str_to_check[i] != "[":
                i += 1
                continue
            for key in self.emo_map.keys():
                emo_tag = f"[{key}]"
                if str_to_check[i : i + len(emo_tag)] == emo_tag:
                    expression_list.append(self.emo_map[key])
                    i += len(emo_tag) - 1
                    break
            i += 1
        return expression_list

    def remove_emotion_keywords(self, target_str: str) -> str:
        lower_str = target_str.lower()
        for key in self.emo_map.keys():
            lower_key = f"[{key}]".lower()
            while lower_key in lower_str:
                start_index = lower_str.find(lower_key)
                end_index = start_index + len(lower_key)
                target_str = target_str[:start_index] + target_str[end_index:]
                lower_str = lower_str[:start_index] + lower_str[end_index:]
        return target_str
