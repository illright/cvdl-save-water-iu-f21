import json
from itertools import islice
from shutil import copy
from os import PathLike, mkdir, scandir
from random import shuffle
from typing import Literal

import numpy as np
import skimage
from mrcnn import model as modellib, utils


def split_dataset(
    dataset_dir: PathLike, ratios: tuple[float, float, float] = (0.8, 0.15, 0.5)
):
    images = list(scandir(dataset_dir / "img"))
    shuffle(images)
    image_iterator = iter(images)
    directories = ("train", "val", "test")

    for directory, ratio in zip(directories, ratios):
        target = dataset_dir / "split" / directory
        mkdir(target)
        for image in islice(image_iterator, len(images) * ratio):
            copy(dataset_dir / "img" / image.name, target)
            copy(dataset_dir / "ann" / f"{image.name}.json", target / "ann")


class TapDataset(utils.Dataset):
    name = "save_water"

    @staticmethod
    def split_coords(points: list[tuple[int, int]]):
        xs: list[int] = []
        ys: list[int] = []

        for point in points:
            xs.append(point[0])
            ys.append(point[1])

        return xs, ys

    def get_class_id(self, class_name: str):
        for class_info in self.class_info:
            if class_info['name'] == class_name:
                return class_info['id']

    def load(self, dataset_dir: PathLike, subset: Literal["train", "val", "test"]):
        meta = json.load(open(dataset_dir / "meta.json"))
        for index, img_class in enumerate(meta["classes"]):
            self.add_class(TapDataset.name, index, img_class["title"])

        subset_dir = dataset_dir / "split" / subset
        for image in scandir(subset_dir):
            if image.is_dir():
                continue

            annotation = json.load(open(subset_dir / "ann" / f"{image.name}.json"))
            self.add_image(
                TapDataset.name,
                image_id=image.name,
                path=image.path,
                width=annotation["size"]["width"],
                height=annotation["size"]["height"],
                points=annotation['objects'][0]['points'],
                class_name=annotation['objects'][0]['classTitle'],
            )

    def load_mask(self, image_idx: int):
        image_info = self.image_info[image_idx]
        class_id = self.get_class_id(image_info['class_name'])

        if image_info["source"] != TapDataset.name:
            return super().load_mask(image_idx)

        mask = np.zeros([image_info["height"], image_info["width"], 1], dtype=np.uint8)
        ext_x_coords, ext_y_coords = TapDataset.split_coords(image_info['points']['exterior'])
        rr, cc = skimage.draw.polygon(ext_x_coords, ext_y_coords)
        mask[rr, cc, 0] = 1

        # TODO: account for interior polygons

        return mask.astype(np.bool), np.array([class_id], dtype=np.int32)
