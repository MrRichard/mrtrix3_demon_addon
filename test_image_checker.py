from ImageTypeChecker import ImageTypeChecker

config_path = "/isilon/datalake/riipl/original/DEMONco/mrtrix3_demon_addon/test_config.json"
directory_path = "/isilon/datalake/riipl/original/DEMONco/mrtrix3_demon_addon/sample_data/3ABMI006356_125300903_20200714/"
checker = ImageTypeChecker(directory_path, config_path)
#print(checker.get_directory_path())
#print(checker.image_data)