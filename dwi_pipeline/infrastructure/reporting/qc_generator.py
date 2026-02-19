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
from matplotlib.collections import LineCollection
import numpy as np
import nibabel as nib
from nibabel.processing import resample_from_to
from scipy.ndimage import zoom

logger = logging.getLogger(__name__)

# Slice positions as fractions through the brain extent (non-zero region)
_SLICE_FRACS = (0.25, 0.50, 0.75)


def _ensure_3d(vol: np.ndarray) -> np.ndarray:
    """Collapse a 4D volume to 3D by averaging along the 4th dimension."""
    if vol.ndim == 4:
        return vol.mean(axis=3)
    return vol


def _get_zooms(affine: np.ndarray) -> np.ndarray:
    """Extract voxel sizes (mm) from a NIfTI affine matrix."""
    return np.sqrt((affine[:3, :3] ** 2).sum(axis=0))


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


def _slice_aspect(zooms: np.ndarray, axis: int) -> float:
    """
    Compute the correct imshow aspect ratio for a slice along *axis*.

    After rot90, the displayed image rows correspond to the 'z-like' dimension
    and columns correspond to the 'x-like' or 'y-like' dimension.  The aspect
    ratio (height-per-width) must reflect the physical voxel sizes so that the
    brain is not squashed or stretched.

    axis=2 (axial):    slice in (X,Y), after rot90 → (Y,X). aspect = vox_y/vox_x
    axis=1 (coronal):  slice in (X,Z), after rot90 → (Z,X). aspect = vox_z/vox_x
    axis=0 (sagittal): slice in (Y,Z), after rot90 → (Z,Y). aspect = vox_z/vox_y
    """
    vx, vy, vz = zooms[0], zooms[1], zooms[2]
    if axis == 2:
        return float(vy / vx)
    elif axis == 1:
        return float(vz / vx)
    else:  # axis == 0
        return float(vz / vy)


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

    b0_img = nib.load(b0_nii)
    b0 = _ensure_3d(b0_img.get_fdata(dtype=np.float32))
    zooms = _get_zooms(b0_img.affine)

    mask = _ensure_3d(nib.load(mask_nii).get_fdata(dtype=np.float32))

    # Resample 5TT from T1w space to DWI space so overlays align correctly.
    fivett_img = nib.load(fivett_nii)
    if fivett_img.shape[:3] != b0_img.shape[:3] or not np.allclose(
        fivett_img.affine, b0_img.affine, atol=1e-3
    ):
        logger.info(
            "Resampling 5TT from %s to DWI space %s",
            fivett_img.shape[:3],
            b0_img.shape[:3],
        )
        fivett_img = resample_from_to(fivett_img, b0_img, order=1)
    fivett = fivett_img.get_fdata(dtype=np.float32)

    brain = _ensure_3d(nib.load(brain_nii).get_fdata(dtype=np.float32))
    parc_dk = _ensure_3d(nib.load(parc_dk_nii).get_fdata(dtype=np.float32))

    results: Dict[str, str] = {}

    # --- Brain mask QC ---
    results["brain_mask_qc"] = str(
        _overlay_mask(b0, mask, zooms, out / "brain_mask_qc.png", "Brain Mask QC")
    )

    # --- 5TT tissue segmentation QC ---
    results["5tt_qc"] = str(
        _overlay_5tt(b0, fivett, zooms, out / "5tt_qc.png")
    )

    # --- Registration QC ---
    results["registration_qc"] = str(
        _overlay_contour(b0, brain, zooms, out / "registration_qc.png", "Registration QC (brain → DWI)")
    )

    # --- DK parcellation QC ---
    results["parcellation_dk_qc"] = str(
        _overlay_parcellation(b0, parc_dk, zooms, out / "parcellation_dk_qc.png", "DK Atlas QC")
    )

    # --- Destrieux parcellation QC ---
    if parc_destrieux_nii:
        parc_dest = _ensure_3d(nib.load(parc_destrieux_nii).get_fdata(dtype=np.float32))
        results["parcellation_destrieux_qc"] = str(
            _overlay_parcellation(b0, parc_dest, zooms, out / "parcellation_destrieux_qc.png", "Destrieux Atlas QC")
        )

    return results


def _overlay_mask(b0: np.ndarray, mask: np.ndarray, zooms: np.ndarray, path: Path, title: str) -> Path:
    """Overlay binary mask as red contour on b0."""
    aspect = _slice_aspect(zooms, axis=2)
    slices = _pick_slices(b0, axis=2)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), facecolor="black")
    for ax, idx in zip(axes, slices):
        bg = _get_axial_slice(b0, idx)
        ov = _get_axial_slice(mask, idx)
        ax.imshow(bg, cmap="gray", interpolation="nearest", aspect=aspect)

        if ov.shape != bg.shape:
            zoom_factors = (bg.shape[0] / ov.shape[0], bg.shape[1] / ov.shape[1])
            ov = zoom(ov, zoom_factors, order=1)

        ax.contour(ov, levels=[0.5], colors=["red"], linewidths=0.8)
        ax.set_title(f"z={idx}", color="white", fontsize=9)
        ax.axis("off")
    fig.suptitle(title, color="white", fontsize=11)
    _save_fig(fig, path)
    return path


def _overlay_5tt(b0: np.ndarray, fivett: np.ndarray, zooms: np.ndarray, path: Path) -> Path:
    """
    Overlay 5TT tissue types on b0.

    5TT volumes: 0=cortGM, 1=subcortGM, 2=WM, 3=CSF, 4=pathological
    Color mapping: GM=red, subcort=orange, WM=blue, CSF=green
    """
    aspect = _slice_aspect(zooms, axis=2)
    slices = _pick_slices(b0, axis=2)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), facecolor="black")

    for ax, idx in zip(axes, slices):
        bg = _get_axial_slice(b0, idx)
        ax.imshow(bg, cmap="gray", interpolation="nearest", aspect=aspect)

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

            if tissue.shape != (h, w):
                zoom_factors = (h / tissue.shape[0], w / tissue.shape[1])
                tissue = zoom(tissue, zoom_factors, order=1)

            for c in range(3):
                rgb[:, :, c] += tissue * color[c]
        rgb = np.clip(rgb, 0, 1)

        alpha = np.clip(rgb.sum(axis=2), 0, 1)
        rgba = np.dstack([rgb, alpha * 0.25])
        ax.imshow(rgba, interpolation="nearest", aspect=aspect)
        ax.set_title(f"z={idx}", color="white", fontsize=9)
        ax.axis("off")

    fig.suptitle("5TT Tissue Segmentation QC", color="white", fontsize=11)
    _save_fig(fig, path)
    return path


def _overlay_contour(b0: np.ndarray, brain: np.ndarray, zooms: np.ndarray, path: Path, title: str) -> Path:
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
        aspect = _slice_aspect(zooms, axis=axis)
        slices = _pick_slices(b0, axis=axis)
        for col, idx in enumerate(slices):
            ax = axes[row, col]
            bg = get_slice_fn(b0, idx)
            ov = get_slice_fn(brain, idx)

            ax.imshow(bg, cmap="gray", interpolation="nearest", aspect=aspect)

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


def _overlay_parcellation(b0: np.ndarray, parc: np.ndarray, zooms: np.ndarray, path: Path, title: str) -> Path:
    """Overlay parcellation labels as semi-transparent discrete colors on b0."""
    aspect = _slice_aspect(zooms, axis=2)
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
        ax.imshow(bg, cmap="gray", interpolation="nearest", aspect=aspect)

        if ov.shape != bg.shape:
            zoom_factors = (bg.shape[0] / ov.shape[0], bg.shape[1] / ov.shape[1])
            ov = zoom(ov, zoom_factors, order=0)  # Nearest neighbor for labels

        rgb = label_colors[np.clip(ov.astype(int), 0, len(label_colors) - 1)]
        alpha = (ov > 0).astype(float) * 0.45
        rgba = np.dstack([rgb, alpha])
        ax.imshow(rgba, interpolation="nearest", aspect=aspect)
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
    zooms = _get_zooms(affine)

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
        aspect = _slice_aspect(zooms, axis=axis)

        fig, ax = plt.subplots(1, 1, figsize=(6, 6), facecolor="black")

        # Show mid-plane background slice
        if axis == 0:
            bg = _get_sagittal_slice(b0, mid_idx)
        elif axis == 1:
            bg = _get_coronal_slice(b0, mid_idx)
        else:
            bg = _get_axial_slice(b0, mid_idx)
        ax.imshow(bg, cmap="gray", interpolation="nearest", aspect=aspect)

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
    slab_width: int = 5,
    max_streamlines: int = 50_000,
):
    """
    Project streamline segments near mid_idx onto the display plane with
    RGB directional coloring (|Δx|→R, |Δy|→G, |Δz|→B in world/RAS space).

    Only segments within ±slab_width voxels of the mid-plane are drawn.
    Streamlines are randomly subsampled to max_streamlines for performance.
    """
    dims = [d for d in range(3) if d != axis]
    max_dim1 = vol_shape[dims[1]] - 1

    # Random subsample to keep rendering fast
    rng = np.random.RandomState(0)
    sl_list = list(streamlines)
    if len(sl_list) > max_streamlines:
        idx = rng.choice(len(sl_list), size=max_streamlines, replace=False)
        sl_list = [sl_list[i] for i in idx]

    all_segments = []
    all_colors = []

    for sl in sl_list:
        # Convert world coords to voxel coords for display positioning
        pts_vox = nib.affines.apply_affine(inv_affine, sl)

        # Keep only points near the mid-plane
        near_mask = np.abs(pts_vox[:, axis] - mid_idx) < slab_width
        if not np.any(near_mask):
            continue

        pts_world_near = sl[near_mask]       # world coords for direction colour
        pts_vox_near = pts_vox[near_mask]    # voxel coords for display position

        if len(pts_world_near) < 2:
            continue

        # Display coords after rot90 mapping
        display_x = pts_vox_near[:, dims[0]]
        display_y = max_dim1 - pts_vox_near[:, dims[1]]

        # Per-segment RGB directional colour: |Δworld| normalised → (R, G, B)
        diffs = np.diff(pts_world_near, axis=0)          # shape (n-1, 3)
        norms = np.linalg.norm(diffs, axis=1, keepdims=True)
        norms = np.where(norms < 1e-6, 1.0, norms)
        dir_rgb = np.abs(diffs / norms)                  # each row in [0,1]³

        for i in range(len(pts_world_near) - 1):
            all_segments.append(
                [(display_x[i], display_y[i]), (display_x[i + 1], display_y[i + 1])]
            )
            all_colors.append((*dir_rgb[i], 0.4))        # RGBA

    if all_segments:
        lc = LineCollection(all_segments, colors=all_colors, linewidths=0.8)
        ax.add_collection(lc)
