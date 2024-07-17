import os
import json
from glob import glob
import subprocess
import nibabel as nib
import shutil

# A class to find NODDI inputs .. as they may vary over time
# If there are no json file files, create a /nifti2 directory and search there

# Example usage:
# config_path = "path/to/config.json"
# directory_path = "path/to/directory"
# checker = ImageTypeChecker(directory_path, config_path)
# print(checker.image_data)

class ImageTypeChecker:
    
    def __init__(self, directory_path, config_path):
        self.directory_path = directory_path
        self.config = self.load_config(config_path)
        self.image_data = self.process_directory()
        self.mrtrix3 = ''

    def load_config(self, config_path):
        with open(config_path) as f:
            return json.load(f)
        
    def get_directory_path(self):
        return self.directory_path

    def process_directory(self):
        image_data = {}
        json_files = glob(os.path.join(self.directory_path,"nifti","*.json"))
        nifti2_created = False
        
        if len(json_files) <= 1:
            nifti2dir=os.path.join(self.directory_path,'nifti2')
            
            if os.path.exists(nifti2dir) == False:
                os.mkdir(nifti2dir)
                nifti2_created = True
            else:
                json_files = glob(os.path.join(nifti2dir, "*.json"))
            
            if len(json_files) <= 1:    
                self.convert_dicom_to_nifti(
                    os.path.join(self.directory_path, 'tmp'),
                    nifti2dir
                )
                json_files = glob(os.path.join(nifti2dir, "*.json"))
          
        i=0
        for json_file in json_files:
            with open(json_file) as f:
                data = json.load(f)
                if "SeriesDescription" in data and any(desc in data["SeriesDescription"] for desc in self.config["SeriesDescriptions"]):
                    i+=1
                    base_name = os.path.splitext(json_file)[0]
                    nii_file = self.find_file(base_name, ["nii", "nii.gz"])
                    if nii_file:
                        bvec_file = self.find_file(base_name, ["bvec"])
                        bval_file = self.find_file(base_name, ["bval"])
                        
                        # classify the data
                        label=self.classify_diffusion_image(data, nii_file)
                        base_name=os.path.basename(base_name)
                        print(f"{label} {base_name}")
                        image_data[label] = {
                            "json_file" : json_file,
                            "nifti_path": nii_file,
                            "bvec_path": bvec_file,
                            "bval_path": bval_file,
                            "direction": data.get("Direction"),
                            "readout_time": data.get("ReadoutTime")
                        }
        self.mrtrix3_inputs = self.create_mrtrix3_inputs(image_data)
        
        if nifti2_created:
            pass
            shutil.rmtree(nifti2dir)
            
        return image_data
    
    def get_mrtrix3_inputs(self):
        return self.mrtrix3_inputs
    
    def create_mrtrix3_inputs(self, image_data):
        mrtrix3_dir = os.path.join(self.directory_path, 'mrtrix3_inputs')
        if not os.path.exists(mrtrix3_dir):
            os.makedirs(mrtrix3_dir)
        
        for label, files in image_data.items():
            for key, file_path in files.items():
                if file_path:
                    ext = os.path.splitext(file_path)[1]
                    new_file_name = f"{label}{ext}"
                    new_file_path = os.path.join(mrtrix3_dir, new_file_name)
                    if os.path.exists(file_path):
                        shutil.copy(file_path, new_file_path)
        return mrtrix3_dir
    
    def convert_dicom_to_nifti(self, dicom_path, output_path):
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        command = f"dcm2niix -o {output_path} -b y {dicom_path}"
        subprocess.run(command, shell=True, check=True)

    def find_file(self, base_name, extensions):
        for ext in extensions:
            file_path = f"{base_name}.{ext}"
            if os.path.exists(file_path):
                return file_path
        return None
    
    
    
    def classify_diffusion_image(self, data, nii_file):
        series_description = data.get("SeriesDescription", "")
        phase_encoding_direction = data.get("PhaseEncodingDirection", "")
        
        direction = "A2P" if "j-" in phase_encoding_direction else "P2A"
        suffix=self.get_image_value_range(nii_file)
        
        if "SBRef" in series_description:
            return f"{direction}_SBREF_{suffix}"
        
        if "PA" in series_description.replace('>',''):
            return f"P2A_{suffix}"
        
        if "AP" in series_description.replace('>',''):
            return f"A2P_{suffix}"
        
        if "MOSAIC" in data.get("ImageType", []):
            return f"{direction}_MOSAIC"
        
        if "PHASE" in data.get("ImageType", []):
            return f"{direction}_PHASE"
        
        return "Unknown image type"
    
    def get_image_value_range(self, nii_file):
        # Implement logic to load the image and get the value range
        # This is a placeholder implementation
        
        if nii_file:
            # Load the NIfTI file and calculate the value range
            img = nib.load(nii_file)
            img_data = img.get_fdata()[:,:,:]
            
            if img_data.min() >= 0:
                return f"MOSAIC"
            if img_data.min() < -1000 and img_data.max() > 1000:
                return f"PHASE"
        return None

