"""
QC image generation for the DWI pipeline.

Pure Python module using nibabel + matplotlib (Agg backend) for fully headless
rendering of quality-control overlay images.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import nibabel as nib
from scipy.ndimage import zoom

logger = logging.getLogger(__name__)

# Slice positions as fractions through the brain extent (non-zero region)
_SLICE_FRACS = (0.25, 0.50, 0.75)


def _ensure_3d(vol: np.ndarray) -> np.ndarray:
    """Collapse a 4D volume to 3D by averaging along the 4th dimension."""
    if vol.ndim == 4:
        return vol.mean(axis=3)
    return vol


def _brain_extent(data: np.ndarray, axis: int):
    """Return (lo, hi) indices along *axis* that bracket non-zero voxels."""
    collapsed = np.any(data != 0, axis=tuple(i for i in range(data.ndim) if i != axis))
    nonzero_idx = np.where(collapsed)[0]
    if len(nonzero_idx) == 0:
        return 0, data.shape[axis] - 1
    return int(nonzero_idx[0]), int(nonzero_idx[-1])


def _pick_slices(data: np.ndarray, axis: int, fracs=_SLICE_FRACS):
    """Pick slice indices at given fractions through the brain extent along *axis*."""
    lo, hi = _brain_extent(data, axis)
    return [int(lo + f * (hi - lo)) for f in fracs]


def _get_axial_slice(vol: np.ndarray, idx: int) -> np.ndarray:
    """Return an axial (z) slice, oriented for display."""
    return np.rot90(vol[:, :, idx])


def _get_sagittal_slice(vol: np.ndarray, idx: int) -> np.ndarray:
    return np.rot90(vol[idx, :, :])


def _get_coronal_slice(vol: np.ndarray, idx: int) -> np.ndarray:
    return np.rot90(vol[:, idx, :])


def _save_fig(fig, path: Path):
    fig.savefig(str(path), dpi=150, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    logger.info("Saved QC image: %s", path)


# --------------------------------------------------------------------------- #
#  Overlay QC
# --------------------------------------------------------------------------- #

def generate_overlay_qc(
    b0_nii: str,
    mask_nii: str,
    fivett_nii: str,
    brain_nii: str,
    parc_dk_nii: str,
    parc_destrieux_nii: Optional[str],
    out_dir: str,
) -> Dict[str, str]:
    """
    Generate overlay QC images from NIfTI files.

    Returns a dict mapping image name to the saved PNG path.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    b0 = _ensure_3d(nib.load(b0_nii).get_fdata(dtype=np.float32))
    mask = _ensure_3d(nib.load(mask_nii).get_fdata(dtype=np.float32))
    fivett = nib.load(fivett_nii).get_fdata(dtype=np.float32)
    brain = _ensure_3d(nib.load(brain_nii).get_fdata(dtype=np.float32))
    parc_dk = _ensure_3d(nib.load(parc_dk_nii).get_fdata(dtype=np.float32))

    results: Dict[str, str] = {}

    # --- Brain mask QC ---
    results["brain_mask_qc"] = str(
        _overlay_mask(b0, mask, out / "brain_mask_qc.png", "Brain Mask QC")
    )

    # --- 5TT tissue segmentation QC ---
    results["5tt_qc"] = str(
        _overlay_5tt(b0, fivett, out / "5tt_qc.png")
    )

    # --- Registration QC ---
    results["registration_qc"] = str(
        _overlay_contour(b0, brain, out / "registration_qc.png", "Registration QC (brain → DWI)")
    )

    # --- DK parcellation QC ---
    results["parcellation_dk_qc"] = str(
        _overlay_parcellation(b0, parc_dk, out / "parcellation_dk_qc.png", "DK Atlas QC")
    )

    # --- Destrieux parcellation QC ---
    if parc_destrieux_nii:
        parc_dest = _ensure_3d(nib.load(parc_destrieux_nii).get_fdata(dtype=np.float32))
        results["parcellation_destrieux_qc"] = str(
            _overlay_parcellation(b0, parc_dest, out / "parcellation_destrieux_qc.png", "Destrieux Atlas QC")
        )

    return results


def _overlay_mask(b0: np.ndarray, mask: np.ndarray, path: Path, title: str) -> Path:
    """Overlay binary mask as red contour on b0."""
    from scipy.ndimage import zoom

    slices = _pick_slices(b0, axis=2)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), facecolor="black")
    for ax, idx in zip(axes, slices):
        bg = _get_axial_slice(b0, idx)
        ov = _get_axial_slice(mask, idx)
        ax.imshow(bg, cmap="gray", interpolation="nearest")

        # Resize ov to match background dimensions if needed
        if ov.shape != bg.shape:
            # Calculate zoom factors for resizing
            zoom_factors = (bg.shape[0] / ov.shape[0], bg.shape[1] / ov.shape[1])
            ov = zoom(ov, zoom_factors, order=1)  # Linear interpolation

        ax.contour(ov, levels=[0.5], colors=["red"], linewidths=0.8)
        ax.set_title(f"z={idx}", color="white", fontsize=9)
        ax.axis("off")
    fig.suptitle(title, color="white", fontsize=11)
    _save_fig(fig, path)
    return path


def _overlay_5tt(b0: np.ndarray, fivett: np.ndarray, path: Path) -> Path:
    """
    Overlay 5TT tissue types on b0.

    5TT volumes: 0=cortGM, 1=subcortGM, 2=WM, 3=CSF, 4=pathological
    Color mapping: GM=red, subcort=orange, WM=blue, CSF=green
    """
    from scipy.ndimage import zoom

    slices = _pick_slices(b0, axis=2)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), facecolor="black")

    for ax, idx in zip(axes, slices):
        bg = _get_axial_slice(b0, idx)
        ax.imshow(bg, cmap="gray", interpolation="nearest")

        # Build composite RGB overlay from tissue volumes
        h, w = bg.shape
        rgb = np.zeros((h, w, 3), dtype=np.float32)
        colors = [
            (1.0, 0.0, 0.0),   # cortGM → red
            (1.0, 0.6, 0.0),   # subcortGM → orange
            (0.0, 0.3, 1.0),   # WM → blue
            (0.0, 1.0, 0.0),   # CSF → green
        ]
        for tissue_idx, color in enumerate(colors):
            if tissue_idx >= fivett.shape[3]:
                break
            tissue = _get_axial_slice(fivett[:, :, :, tissue_idx], idx)

            # Resize tissue to match background dimensions if needed
            if tissue.shape != (h, w):
                # Calculate zoom factors for resizing
                zoom_factors = (h / tissue.shape[0], w / tissue.shape[1])
                tissue = zoom(tissue, zoom_factors, order=1)  # Linear interpolation

            for c in range(3):
                rgb[:, :, c] += tissue * color[c]
        rgb = np.clip(rgb, 0, 1)

        # Only show where there is tissue
        alpha = np.clip(rgb.sum(axis=2), 0, 1)
        rgba = np.dstack([rgb, alpha * 0.5])
        ax.imshow(rgba, interpolation="nearest")
        ax.set_title(f"z={idx}", color="white", fontsize=9)
        ax.axis("off")

    fig.suptitle("5TT Tissue Segmentation QC", color="white", fontsize=11)
    _save_fig(fig, path)
    return path


def _overlay_contour(b0: np.ndarray, brain: np.ndarray, path: Path, title: str) -> Path:
    """
    Overlay brain edges as contours on b0 in all three planes.

    Produces a 3-row × 3-column grid:
      Row 0: axial slices    (axis=2)
      Row 1: coronal slices  (axis=1)
      Row 2: sagittal slices (axis=0)
    """
    plane_configs = [
        ("Axial",    2, _get_axial_slice),
        ("Coronal",  1, _get_coronal_slice),
        ("Sagittal", 0, _get_sagittal_slice),
    ]

    fig, axes = plt.subplots(3, 3, figsize=(12, 12), facecolor="black")
    fig.subplots_adjust(hspace=0.05, wspace=0.05)

    for row, (plane_label, axis, get_slice_fn) in enumerate(plane_configs):
        slices = _pick_slices(b0, axis=axis)
        for col, idx in enumerate(slices):
            ax = axes[row, col]
            bg = get_slice_fn(b0, idx)
            ov = get_slice_fn(brain, idx)

            ax.imshow(bg, cmap="gray", interpolation="nearest")

            if ov.shape != bg.shape:
                zoom_factors = (bg.shape[0] / ov.shape[0], bg.shape[1] / ov.shape[1])
                ov = zoom(ov, zoom_factors, order=1)

            thresh = ov > (np.percentile(ov[ov > 0], 10) if np.any(ov > 0) else 0)
            ax.contour(thresh.astype(float), levels=[0.5], colors=["cyan"], linewidths=0.8)

            label = f"{plane_label} [{axis}]={idx}" if col == 0 else f"[{axis}]={idx}"
            ax.set_title(label, color="white", fontsize=8)
            ax.axis("off")

    fig.suptitle(title, color="white", fontsize=12)
    _save_fig(fig, path)
    return path


def _overlay_parcellation(b0: np.ndarray, parc: np.ndarray, path: Path, title: str) -> Path:
    """Overlay parcellation labels as semi-transparent discrete colors on b0."""
    from scipy.ndimage import zoom

    slices = _pick_slices(b0, axis=2)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), facecolor="black")

    # Build a random but reproducible colormap for integer labels
    n_labels = int(parc.max()) + 1
    rng = np.random.RandomState(42)
    label_colors = rng.rand(max(n_labels, 1), 3)
    label_colors[0] = 0  # label 0 = background → black

    for ax, idx in zip(axes, slices):
        bg = _get_axial_slice(b0, idx)
        ov = _get_axial_slice(parc, idx).astype(int)
        ax.imshow(bg, cmap="gray", interpolation="nearest")

        # Resize ov to match background dimensions if needed
        if ov.shape != bg.shape:
            # Calculate zoom factors for resizing
            zoom_factors = (bg.shape[0] / ov.shape[0], bg.shape[1] / ov.shape[1])
            ov = zoom(ov, zoom_factors, order=0)  # Nearest neighbor for labels

        # Map labels to RGB
        rgb = label_colors[np.clip(ov.astype(int), 0, len(label_colors) - 1)]
        alpha = (ov > 0).astype(float) * 0.45
        rgba = np.dstack([rgb, alpha])
        ax.imshow(rgba, interpolation="nearest")
        ax.set_title(f"z={idx}", color="white", fontsize=9)
        ax.axis("off")

    fig.suptitle(title, color="white", fontsize=11)
    _save_fig(fig, path)
    return path


# --------------------------------------------------------------------------- #
#  Tract QC
# --------------------------------------------------------------------------- #

def generate_tract_qc(
    b0_nii: str,
    tck_file: str,
    out_dir: str,
) -> Dict[str, str]:
    """
    Generate tractography QC images by projecting streamlines onto orthogonal planes.

    Returns a dict mapping image name to the saved PNG path.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    b0_img = nib.load(b0_nii)
    b0 = _ensure_3d(b0_img.get_fdata(dtype=np.float32))
    affine = b0_img.affine
    inv_affine = np.linalg.inv(affine)

    # Load streamlines
    tck = nib.streamlines.load(tck_file)
    streamlines = tck.streamlines

    results: Dict[str, str] = {}

    planes = [
        ("sagittal", 0, "tracts_sagittal_qc.png"),
        ("coronal", 1, "tracts_coronal_qc.png"),
        ("axial", 2, "tracts_axial_qc.png"),
    ]

    for plane_name, axis, fname in planes:
        lo, hi = _brain_extent(b0, axis)
        mid_idx = (lo + hi) // 2

        fig, ax = plt.subplots(1, 1, figsize=(6, 6), facecolor="black")

        # Show mid-plane background slice
        if axis == 0:
            bg = _get_sagittal_slice(b0, mid_idx)
        elif axis == 1:
            bg = _get_coronal_slice(b0, mid_idx)
        else:
            bg = _get_axial_slice(b0, mid_idx)
        ax.imshow(bg, cmap="gray", interpolation="nearest", aspect="equal")

        # Project streamlines onto the plane
        _project_streamlines(ax, streamlines, inv_affine, b0.shape, axis, mid_idx)

        ax.set_title(f"{plane_name.capitalize()} (slice {mid_idx})", color="white", fontsize=10)
        ax.axis("off")
        _save_fig(fig, out / fname)
        results[f"tracts_{plane_name}_qc"] = str(out / fname)

    return results


def _project_streamlines(
    ax,
    streamlines,
    inv_affine: np.ndarray,
    vol_shape: tuple,
    axis: int,
    mid_idx: int,
    slab_width: int = 3,
):
    """
    Project streamline segments near mid_idx onto the display plane.

    Only segments within ±slab_width voxels of the mid-plane are drawn, to keep
    the image from being overwhelmed.
    """
    # Map axis → which image dimensions to use for x/y
    # After rot90, the display is (rows, cols) so we need to map voxel coords
    # to the rotated display space
    for sl in streamlines:
        # Convert world coords to voxel coords
        pts = nib.affines.apply_affine(inv_affine, sl)

        # Keep only segments near the mid-plane
        near_mask = np.abs(pts[:, axis] - mid_idx) < slab_width
        if not np.any(near_mask):
            continue

        # Get the two non-axis dimensions
        dims = [d for d in range(3) if d != axis]

        # Extract x/y in voxel space
        vx = pts[near_mask, dims[0]]
        vy = pts[near_mask, dims[1]]

        # Match rot90 transform: display_row = max_col - col, display_col = row
        # For axial (axis=2): dims=[0,1], rot90 maps (x,y) → (max_y - y, x)
        # For sagittal (axis=0): dims=[1,2], rot90 maps (y,z) → (max_z - z, y)
        # For coronal (axis=1): dims=[0,2], rot90 maps (x,z) → (max_z - z, x)
        max_dim1 = vol_shape[dims[1]] - 1
        display_x = vx
        display_y = max_dim1 - vy

        ax.plot(display_x, display_y, color="orange", alpha=0.03, linewidth=0.3)
