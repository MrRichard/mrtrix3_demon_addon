#!/bin/bash
# Create output directory for QC images
mxoutputs=`find ${1}/DTI* -maxdepth 1 -type d -name "mrtrix3_outputs"`

if [[ ! -d ${mxoutputs} ]]; then 
    echo "Missing mrtrix output directory"
    exit 1
fi 
mkdir -p ${mxoutputs}/qc_images

# Segmentation visualization using mrview's lightbox mode
echo "b0_5tt_mosaic"
mrview ${mxoutputs}/mean_b0_processed.nii.gz \
    -mode 4 \
    -overlay.load ${mxoutputs}/5tt_coreg.mif \
    -overlay.opacity 0.4 \
    -capture.folder ${mxoutputs}/qc_images \
    -capture.prefix b0_5tt_mosaic \
    -capture.grab \
    -exit

echo "t1_5tt_mosaic"
mrview ${mxoutputs}/anat.mif \
    -mode 4 \
    -overlay.load ${mxoutputs}/5tt_nocoreg.mif \
    -overlay.opacity 0.4 \
    -capture.folder ${mxoutputs}/qc_images \
    -capture.prefix t1_5tt_mosaic \
    -capture.grab \
    -exit

echo "tissue_ROI_overlay"
mrview ${mxoutputs}/mean_b0_processed.nii.gz \
    -mode 4 \
    -overlay.load ${mxoutputs}/dwi_Brainnetome.nii.gz \
    -overlay.opacity 0.6 \
    -overlay.colourmap 6 \
    -overlay.interpolation false \
    -capture.folder ${mxoutputs}/qc_images \
    -capture.prefix tissue_ROI_overlay \
    -capture.grab \
    -exit

# Tissue segmentation visualization
echo "tissue_seg_overlay"
mrview ${mxoutputs}/mean_b0_processed.nii.gz \
    -mode 4 \
    -overlay.load ${mxoutputs}/5tt_coreg.mif \
    -overlay.opacity 0.4 \
    -capture.folder ${mxoutputs}/qc_images \
    -capture.prefix tissue_seg_overlay \
    -capture.grab \
    -exit

# Brain mask visualization in lightbox mode
echo "brain_mask_overlay"
mrview ${mxoutputs}/mean_b0_processed.nii.gz \
    -mode 4 \
    -overlay.load ${mxoutputs}/mask.mif \
    -overlay.opacity 0.4 \
    -overlay.colourmap 1 \
    -overlay.interpolation false \
    -capture.folder ${mxoutputs}/qc_images \
    -capture.prefix brain_mask_overlay \
    -capture.grab \
    -exit

# Response function visualization
echo "response_function_voxels"

if [[ -f "${mxoutputs}/voxels_hollander.mif" ]]; then 
    mrview ${mxoutputs}/mean_b0_processed.nii.gz \
        -mode 4 \
        -overlay.load ${mxoutputs}/voxels_hollander.mif \
        -overlay.opacity 0.4 \
        -orientationlabel true \
        -noannotations \
        -capture.folder ${mxoutputs}/qc_images \
        -capture.prefix response_function_voxels \
        -capture.grab \
        -exit
fi 

if [[ -f "${mxoutputs}/voxels_tournier.mif" ]]; then 
    mrview ${mxoutputs}/mean_b0_processed.nii.gz \
        -mode 4 \
        -overlay.load ${mxoutputs}/voxels_tournier.mif \
        -overlay.opacity 0.4 \
        -orientationlabel true \
        -noannotations \
        -capture.folder ${mxoutputs}/qc_images \
        -capture.prefix response_function_voxels \
        -capture.grab \
        -exit
fi 

# Tractography visualizations

if [[ -f "${mxoutputs}/sift_1M_hollander.tck" ]]; then
    tractfile="${mxoutputs}/sift_1M_hollander.tck"
fi

if [[ -f "${mxoutputs}/sift_1M_tournier.tck" ]]; then
    tractfile="${mxoutputs}/sift_1M_tournier.tck"
fi

# Sagittal view
echo "tracts_sagittal"
mrview ${mxoutputs}/mean_b0_processed.nii.gz \
    -mode 1 \
    -tractography.load ${tractfile} \
    -plane 0 \
    -tractography.opacity 0.5 \
    -capture.folder ${mxoutputs}/qc_images \
    -capture.prefix tracts_sagittal \
    -capture.grab \
    -exit

# Coronal view
echo "tracts_coronal"
mrview ${mxoutputs}/mean_b0_processed.nii.gz \
    -mode 1 \
    -tractography.load ${tractfile} \
    -tractography.opacity 0.5 \
    -plane 1 \
    -noannotations \
    -capture.folder ${mxoutputs}/qc_images \
    -capture.prefix tracts_coronal \
    -capture.grab \
    -exit

# Axial view
echo "tracts_axial"
mrview ${mxoutputs}/mean_b0_processed.nii.gz \
    -mode 1 \
    -tractography.load ${tractfile} \
    -tractography.opacity 0.5 \
    -plane 2 \
    -noannotations \
    -capture.folder ${mxoutputs}/qc_images \
    -capture.prefix tracts_axial \
    -capture.grab \
    -exit
