#!/usr/bin/env bash

LIST="mni-flairs.txt"

while IFS= read -r img; do
  [[ -z "$img" ]] && continue

  if [[ ! -f "$img" ]]; then
    echo "Image not found: $img"
    continue
  fi

  img_dir=$(dirname "$img")
  mask="WM-mask.nii.gz"

  if [[ ! -f "$mask" ]]; then
    echo "Mask not found: $img"
    continue
  fi

  # total WM voxels
  total_vox=$(fslstats "$mask" -V | awk '{print $1}')

  # create binary image mask (valid data = nonzero)
  tmp_imgmask=$(mktemp /tmp/imgmask_XXXXXX.nii.gz)
  fslmaths "$img" -thr 1e-6 -bin "$tmp_imgmask"

  # voxels in WM mask that DO overlap image data
  tmp_overlap=$(mktemp /tmp/overlap_XXXXXX.nii.gz)
  fslmaths "$mask" -mas "$tmp_imgmask" "$tmp_overlap"

  overlap_vox=$(fslstats "$tmp_overlap" -V | awk '{print $1}')

  # missing voxels = WM not covered by image
  missing_vox=$(( total_vox - overlap_vox ))

  # percent missing
  pct_missing=$(awk -v m="$missing_vox" -v t="$total_vox" 'BEGIN {
    if (t>0) printf "%.2f", (m/t)*100;
    else print "0.00"
  }')

  rm -f "$tmp_imgmask" "$tmp_overlap"

  echo "$img -> Missing WM voxels: $missing_vox ($pct_missing%)"

done < "$LIST"
