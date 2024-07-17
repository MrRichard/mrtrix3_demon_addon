from ImageTypeChecker import ImageTypeChecker

config_path = "/isilon/datalake/riipl/original/DEMONco/mrtrix3_demon_addon/config.json"
directory_path = "/isilon/datalake/riipl/original/DEMONco/mrtrix3_demon_addon/sample_data/3AEMC003616_125300457_20191212/"
checker = ImageTypeChecker(directory_path, config_path)
#print(checker.get_directory_path())
#print(checker.image_data)