# Create output directory for QC images
mkdir -p ${1}/DTI/mrtrix3_outputs/qc_images

# Segmentation visualization using mrview's lightbox mode
echo "b0_5tt_mosaic"
mrview ${1}/DTI/mrtrix3_outputs/mean_b0_processed.nii.gz \
    -mode 4 \
    -overlay.load ${1}/DTI/mrtrix3_outputs/5tt_coreg.mif \
    -overlay.opacity 0.4 \
    -noannotations \
    -orientationlabel true \
    -capture.prefix ${1}/DTI/mrtrix3_outputs/qc_images/b0_5tt_mosaic \
    -capture.grab \
    -exit

echo "t1_5tt_mosaic"
mrview ${1}/DTI/mrtrix3_outputs/anat.mif \
    -mode 4 \
    -overlay.load ${1}/DTI/mrtrix3_outputs/5tt_nocoreg.mif \
    -overlay.opacity 0.4 \
    -orientationlabel true \
    -noannotations \
    -capture.prefix ${1}/DTI/mrtrix3_outputs/qc_images/t1_5tt_mosaic \
    -capture.grab \
    -exit

echo "tissue_ROI_overlay"
mrview ${1}/DTI/mrtrix3_outputs/mean_b0_processed.nii.gz \
    -mode 4 \
    -overlay.load ${1}/DTI/mrtrix3_outputs/dwi_Brainnetome.nii.gz \
    -overlay.opacity 0.6 \
    -overlay.colourmap 6 \
    -overlay.interpolation false \
    -noannotations \
    -orientationlabel true \
    -capture.prefix ${1}/DTI/mrtrix3_outputs/qc_images/tissue_ROI_overlay \
    -capture.grab \
    -exit

# Tissue segmentation visualization
echo "tissue_seg_overlay"
mrview ${1}/DTI/mrtrix3_outputs/mean_b0_processed.nii.gz \
    -mode 4 \
    -overlay.load ${1}/DTI/mrtrix3_outputs/5tt_coreg.mif \
    -overlay.opacity 0.4 \
    -orientationlabel true \
    -noannotations \
    -capture.prefix ${1}/DTI/mrtrix3_outputs/qc_images/tissue_seg_overlay \
    -capture.grab \
    -exit

# Brain mask visualization in lightbox mode
echo "brain_mask_overlay"
mrview ${1}/DTI/mrtrix3_outputs/mean_b0_processed.nii.gz \
    -mode 4 \
    -overlay.load ${1}/DTI/mrtrix3_outputs/mask.mif \
    -overlay.opacity 0.4 \
    -orientationlabel true \
    -overlay.colourmap 1 \
    -overlay.interpolation false \
    -noannotations \
    -capture.prefix ${1}/DTI/mrtrix3_outputs/qc_images/brain_mask_overlay \
    -capture.grab \
    -exit

# Response function visualization
echo "response_function_voxels"
mrview ${1}/DTI/mrtrix3_outputs/mean_b0_processed.nii.gz \
    -mode 4 \
    -overlay.load ${1}/DTI/mrtrix3_outputs/voxels_hollander.mif \
    -overlay.opacity 0.4 \
    -orientationlabel true \
    -noannotations \
    -capture.prefix ${1}/DTI/mrtrix3_outputs/qc_images/response_function_voxels \
    -capture.grab \
    -exit

# Tractography visualizations

# Sagittal view
echo "tracts_sagittal"
mrview ${1}/DTI/mrtrix3_outputs/mean_b0_processed.nii.gz \
    -mode 1 \
    -tractography.load ${1}/DTI/mrtrix3_outputs/sift_1M_hollander.tck \
    -plane 0 \
    -tractography.opacity 0.5 \
    -capture.folder ${1}/DTI/mrtrix3_outputs/qc_images \
    -capture.prefix tracts_sagittal \
    -capture.grab \
    -exit

# Coronal view
echo "tracts_coronal"
mrview ${1}/DTI/mrtrix3_outputs/mean_b0_processed.nii.gz \
    -mode 1 \
    -tractography.load ${1}/DTI/mrtrix3_outputs/sift_1M_hollander.tck \
    -tractography.opacity 0.5 \
    -plane 1 \
    -noannotations \
    -capture.folder ${1}/DTI/mrtrix3_outputs/qc_images \
    -capture.prefix tracts_coronal \
    -capture.grab \
    -exit

# Axial view
echo "tracts_axial"
mrview ${1}/DTI/mrtrix3_outputs/mean_b0_processed.nii.gz \
    -mode 1 \
    -tractography.load ${1}/DTI/mrtrix3_outputs/sift_1M_hollander.tck \
    -tractography.opacity 0.5 \
    -plane 2 \
    -noannotations \
    -capture.folder ${1}/DTI/mrtrix3_outputs/qc_images \
    -capture.prefix tracts_axial \
    -capture.grab \
    -exit

# FOD visualization
# mrview ${1}/DTI/mrtrix3_outputs/mean_b0_processed.nii.gz \
#     -mode 2 \
#     -load ${1}/DTI/mrtrix3_outputs/wmfod_norm_hollander.mif \
#     -odf.load_sh ${1}/DTI/mrtrix3_outputs/wmfod_norm_hollander.mif \
#     -noannotations \
#     -capture.grab \
#     -capture.prefix ${1}/DTI/mrtrix3_outputs/qc_images/fod_overlay \
#     -exit
