import os
import json
from glob import glob
import subprocess
import nibabel as nib
import shutil

# A class to find NODDI inputs .. as they may vary over time
# If there are no json file files, create a /nifti2 directory and search there

# ENHANCED 7/25/2025: Now supports fieldmap detection and processing for distortion correction

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
        json_files = []
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
                
                # ENHANCED 7/25/2025: Process both DTI and fieldmap data
                if self.is_relevant_sequence(data):
                    i+=1
                    base_name = os.path.splitext(json_file)[0]
                    nii_file = self.find_file(base_name, ["nii", "nii.gz"])
                    if nii_file:
                        bvec_file = self.find_file(base_name, ["bvec"])
                        bval_file = self.find_file(base_name, ["bval"])
                        
                        # ENHANCED 7/25/2025: classify the data (now handles both DTI and fieldmaps)
                        label = self.classify_image(data, nii_file)
                        if label == False:
                            continue

                        base_name=os.path.basename(base_name)
                        print(f"{label} {base_name}")
                        
                        # ENHANCED 7/25/2025: Added echo_time, series_description, and image_type for fieldmap processing
                        image_data[label] = {
                            "json_file" : json_file,
                            "nifti_path": nii_file,
                            "bvec_path": bvec_file,
                            "bval_path": bval_file,
                            "direction": data.get("Direction"),
                            "readout_time": data.get("ReadoutTime"),
                            "echo_time": data.get("EchoTime"),
                            "series_description": data.get("SeriesDescription", ""),
                            "image_type": data.get("ImageType", [])
                        }
        self.mrtrix3_inputs = self.create_mrtrix3_inputs(image_data)
        
        #if nifti2_created:
        #    shutil.rmtree(nifti2dir)
            
        return image_data
    
    # ADDED 7/25/2025: New method to check if this is a DTI or fieldmap sequence we care about
    def is_relevant_sequence(self, data):
        """Check if this is a DTI or fieldmap sequence we care about"""
        series_description = data.get("SeriesDescription", "").upper()
        image_type = data.get("ImageType", [])
        
        # Check for DTI sequences (original logic)
        if any(desc in data.get("SeriesDescription", "") for desc in self.config["SeriesDescriptions"]):
            return True
            
        # ADDED 7/25/2025: Check for fieldmap sequences
        fieldmap_indicators = [
            "FIELDMAP", "FIELD_MAP", "B0MAP", "B0_MAP", 
            "GRE_FIELD_MAPPING", "B0_MAPPING", "DISTORTION"
        ]
        
        if any(indicator in series_description for indicator in fieldmap_indicators):
            return True
            
        # ADDED 7/25/2025: Check for magnitude/phase in image type
        if any(img_type in str(image_type).upper() for img_type in ["MAGNITUDE", "PHASE"]):
            return True
            
        return False
    
    def get_mrtrix3_inputs(self):
        return self.mrtrix3_inputs
    
    def create_mrtrix3_inputs(self, image_data):
        mrtrix3_dir = os.path.join(self.directory_path, 'mrtrix3_inputs')
        if not os.path.exists(mrtrix3_dir):
            os.makedirs(mrtrix3_dir)
        
        for label, files in image_data.items():
            for key, file_path in files.items():
                # ENHANCED 7/25/2025: Only copy NIFTI and JSON files (streamlined logic)
                if file_path and key in ['nifti_path', 'json_file']:
                    # Extract the base name of the file
                    base_name = os.path.basename(file_path)
                    # Handle two-part extensions
                    if '.' in base_name:
                        parts = base_name.rsplit('.', 2)  # Split into at most 3 parts
                        if len(parts) == 3:  # E.g., "file.nii.gz"
                            ext = f".{parts[1]}.{parts[2]}"
                        else:  # E.g., "file.nii" or "file.json"
                            ext = f".{parts[-1]}"
                    else:
                        ext = ''  # No extension
                    
                    new_file_name = f"{label}{ext}"
                    new_file_path = os.path.join(mrtrix3_dir, new_file_name)
                    if os.path.exists(file_path):
                        shutil.copy(file_path, new_file_path)
                        
                # ENHANCED 7/25/2025: Copy bval and bvec files for DTI data
                elif file_path and key in ['bvec_path', 'bval_path']:
                    if 'DTI' in label or 'MOSAIC' in label:
                        base_name = os.path.basename(file_path)
                        ext = f".{base_name.split('.')[-1]}"
                        new_file_name = f"{label}{ext}"
                        new_file_path = os.path.join(mrtrix3_dir, new_file_name)
                        if os.path.exists(file_path):
                            shutil.copy(file_path, new_file_path)
                            
        return mrtrix3_dir
    
    def convert_dicom_to_nifti(self, dicom_path, output_path):
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        command = f"dcm2niix -z y -m y -b y -i y -s y -o {output_path} {dicom_path}"
        print(command)
        subprocess.run(command, shell=True, check=True)

    def find_file(self, base_name, extensions):
        for ext in extensions:
            file_path = f"{base_name}.{ext}"
            if os.path.exists(file_path):
                return file_path
        return None
    
    # ENHANCED 7/25/2025: Unified classification method for both DTI and fieldmap images
    def classify_image(self, data, nii_file):
        """Classify both DTI and fieldmap images"""
        series_description = data.get("SeriesDescription", "").upper()
        image_type = data.get("ImageType", [])
        image_type_str = str(image_type).upper()
        
        # First, check if this is a fieldmap
        fieldmap_label = self.classify_fieldmap_image(data, nii_file)
        if fieldmap_label:
            return fieldmap_label
            
        # If not a fieldmap, try DTI classification
        return self.classify_diffusion_image(data, nii_file)
    
    # ADDED 7/25/2025: New method to classify fieldmap images (magnitude and phase)
    def classify_fieldmap_image(self, data, nii_file):
        """Classify fieldmap images (magnitude and phase)"""
        series_description = data.get("SeriesDescription", "").upper()
        image_type = data.get("ImageType", [])
        image_type_str = str(image_type).upper()
        echo_time = data.get("EchoTime", 0)
        
        # Check if this is a fieldmap sequence
        fieldmap_indicators = [
            "FIELDMAP", "FIELD_MAP", "B0MAP", "B0_MAP", 
            "GRE_FIELD_MAPPING", "B0_MAPPING", "DISTORTION"
        ]
        
        is_fieldmap_sequence = any(indicator in series_description for indicator in fieldmap_indicators)
        
        # Check for magnitude/phase in image type
        has_magnitude = "MAGNITUDE" in image_type_str
        has_phase = "PHASE" in image_type_str
        
        if is_fieldmap_sequence or has_magnitude or has_phase:
            if has_magnitude:
                # Determine which magnitude image (TE1 or TE2)
                if echo_time < 0.005:  # Typically TE1 is around 2-3ms
                    return "FIELDMAP_MAG1"
                else:  # TE2 is typically around 5-7ms
                    return "FIELDMAP_MAG2"
            elif has_phase or "PHASEDIFF" in series_description:
                return "FIELDMAP_PHASEDIFF"
            elif is_fieldmap_sequence:
                # If it's a fieldmap sequence but no explicit type, guess based on echo time
                if echo_time < 0.005:
                    return "FIELDMAP_MAG1"
                else:
                    return "FIELDMAP_MAG2"
        
        return None
    
    def classify_diffusion_image(self, data, nii_file):
        """Original DTI classification logic"""
        series_description = data.get("SeriesDescription", "")
        phase_encoding_direction = data.get("PhaseEncodingDirection", "")
        
        direction = "A2P" if "j-" in phase_encoding_direction else "P2A"
        suffix = self.get_image_value_range(nii_file)

        if suffix == None:
            return False
        
        if "SBRef" in series_description:
            return f"{direction}_SBREF_{suffix}"
        
        if "PA" in series_description.replace('>',''):
            return f"P2A_{suffix}"
        
        if "AP" in series_description.replace('>',''):
            return f"A2P_{suffix}"
        
        if ("AP" not in series_description and "PA" not in series_description):
            return f"A2P_{suffix}"
        
        return False
    
    def get_image_value_range(self, nii_file):
        """Determine if image is MOSAIC (DTI data) or PHASE based on value range"""
        if nii_file:
            try: 
                img = nib.load(nii_file)
                img_data = img.get_fdata()[:,:,:]
                
                if img_data.min() >= 0:
                    return f"MOSAIC"
                if img_data.min() < -1000 and img_data.max() > 1000:
                    return f"PHASE"
            except Exception as e:
                print(f"Error processing NIfTI file {nii_file}: {e}")
                
        return None

    # ADDED 7/25/2025: New method to get summary of detected fieldmap files
    def get_fieldmap_summary(self):
        """Get summary of detected fieldmap files"""
        fieldmap_files = {}
        for label, data in self.image_data.items():
            if label.startswith('FIELDMAP_'):
                fieldmap_files[label] = {
                    'file': data['nifti_path'],
                    'echo_time': data.get('echo_time', 0),
                    'series_description': data.get('series_description', '')
                }
        return fieldmap_files