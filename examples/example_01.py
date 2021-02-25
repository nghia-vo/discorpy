#============================================================================
# Copyright (c) 2018 Diamond Light Source Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#============================================================================
# Author: Nghia T. Vo
# E-mail: nghia.vo@diamond.ac.uk
# Description: Python implementation of the author's methods of
# distortion correction, Nghia T. Vo et al "Radial lens distortion
# correction with sub-pixel accuracy for X-ray micro-tomography"
# Optics Express 23, 32859-32868 (2015), https://doi.org/10.1364/OE.23.032859
# Publication date: 10th July 2018
#============================================================================

import timeit
import numpy as np
import discorpy.losa.loadersaver as io
import discorpy.prep.preprocessing as prep
import discorpy.proc.processing as proc
import discorpy.post.postprocessing as post

"""
Example to show how to use most of the methods in the package.

"""
time_start = timeit.default_timer()
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Initial parameters
file_path = "../data/dot_pattern_03.jpg"
output_base = "E:/correction/"
num_coef = 5  # Number of polynomial coefficients
norm = False  # Correct non-uniform background if True
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------

# Load an image, get shape
print("Load image: {}".format(file_path))
mat0 = io.load_image(file_path)
(height, width) = mat0.shape

# Optional step: correct non-uniform background for global thresholding method.
# Background is generated by applying a strong low-pass filter to the image.
# Then, the image is normalized with the background.
if norm is True:
    mat1 = prep.normalization_fft(mat0, sigma=5, pad=30)
else:
    mat1 = np.copy(mat0)

# Binarization using Otsu's method if thres = None
# Cropped image (30% of the size around the middle) is used for calculating
# the threshold. This is to avoid a case which a dot-pattern doesn't
# cover the whole field of view of a camera.
mat1 = prep.binarization(mat1, ratio=0.3, thres=None)
check = prep.check_num_dots(mat1)
if check:
    raise ValueError(
        "Number of objects detected is not enough !!! Parameters of"
        " the binarization method need to be adjusted!!!")
io.save_image(output_base + "/binarized_image.tif", mat1)

# Calculate the median dot size and the median distance of two nearest dots
# using the middle part of the image (30%). This is based on an assumption
# that there's no distortion around the middle part of the image.
(dot_size, dot_dist) = prep.calc_size_distance(mat1, ratio=0.3)
print("Median size of dots: {0}\nMedian distance between two dots: {1}".format(
    dot_size, dot_dist))

# Select dots with size in the range of [dot_size - dot_size*ratio; dot_size +
# dot_size*ratio]
mat1 = prep.select_dots_based_size(mat1, dot_size, ratio=0.3)
io.save_image(output_base + "/cleaned_1_image.tif", mat1)

# Select dots with the ratio between the major axis and the minor axis (of a
# fitted ellipse) in the range of (1; 1 + ratio).
mat1 = prep.select_dots_based_ratio(mat1, ratio=0.5)
io.save_image(output_base + "/cleaned_2_image.tif", mat1)

# Calculate the horizontal slope and the vertical slope of the grid using the
# middle part of the image (30%).
hor_slope = prep.calc_hor_slope(mat1, ratio=0.3)
ver_slope = prep.calc_ver_slope(mat1, ratio=0.3)
print("Horizontal slope: {0}\nVertical slope: {1}".format(hor_slope, ver_slope))

# Group dots into lines. The method searches nearby dots and decide if they
# belong to the same line or not. The search-range in x-direction is
# defined by num_dot_miss and the search-range in y-direction is defined
# by the slope and the acceptable variation. Only lines with the number of
# dots >= 70% of the maximum number of dots on a line are kept.

list_hor_lines = prep.group_dots_hor_lines(mat1, hor_slope, dot_dist, ratio=0.3,
                                           num_dot_miss=6, accepted_ratio=0.7)
list_ver_lines = prep.group_dots_ver_lines(mat1, ver_slope, dot_dist, ratio=0.3,
                                           num_dot_miss=6, accepted_ratio=0.7)
io.save_plot_image(output_base + "/group_horizontal_dots.png", list_hor_lines,
                   height, width)
io.save_plot_image(output_base + "/group_vertical_dots.png", list_ver_lines,
                   height, width)

# Optional step: Remove residual dots.
# The method uses coordinates of dots on each line for parabolic fit, then
# remove dots with distance to the fitted parabolas greater than 2.0 pixel.
list_hor_lines = prep.remove_residual_dots_hor(
    list_hor_lines, hor_slope, residual=2.0)
list_ver_lines = prep.remove_residual_dots_ver(
    list_ver_lines, ver_slope, residual=2.0)
io.save_plot_image(output_base + "/horizontal_dots_refined.png",
                   list_hor_lines, height, width)
io.save_plot_image(output_base + "/vertical_dots_refined.png",
                   list_ver_lines, height, width)
time_stop = timeit.default_timer()
print("Group dots into horizontal lines and vertical lines in {}"
      " second!".format(time_stop - time_start))

# Optional step: check if the distortion is significant.
list_hor_data = post.calc_residual_hor(list_hor_lines, 0.0, 0.0)
io.save_residual_plot(output_base + "/residual_horizontal_dots_before.png",
                      list_hor_data, height, width)
list_ver_data = post.calc_residual_ver(list_ver_lines, 0.0, 0.0)
io.save_residual_plot(output_base + "/residual_vertical_dots_before.png",
                      list_ver_data, height, width)
check1 = post.check_distortion(list_hor_data)
check2 = post.check_distortion(list_ver_data)
if (not check1) and (not check2):
    print("!!! Distortion is not significant !!!")

# Calculate the center of distortion. xcenter is the center from the left
# of the image. ycenter is the center from the top of the image.
(xcenter, ycenter) = proc.find_cod_coarse(list_hor_lines, list_ver_lines)
print("\nCenter of distortion:\nx-center (from the left of the image): "
      "{0}\ny-center (from the top of the image): {1}\n".format(
        xcenter, ycenter))
# Note: Use fine-search if there's no perspective distortion
# (xcenter, ycenter) = proc.find_cod_fine(
#     list_hor_lines, list_ver_lines, xcenter, ycenter, dot_dist)

# -----------------------------------------------------------------------------
# Calculate distortion coefficients of a backward model.
# -----------------------------------------------------------------------------
time_start = timeit.default_timer()
list_fact = proc.calc_coef_backward(list_hor_lines, list_ver_lines, xcenter,
                                    ycenter, num_coef)

# Apply distortion correction
corrected_mat = post.unwarp_image_backward(mat0, xcenter, ycenter, list_fact)
io.save_image(output_base + "/corrected_image_bw.tif", corrected_mat)
io.save_image(output_base + "/diff_corrected_image_bw.tif",
              np.abs(corrected_mat - mat0))
io.save_metadata_txt(output_base + "/coefficients_bw.txt", xcenter, ycenter,
                     list_fact)

# Check the correction results
list_uhor_lines = post.unwarp_line_backward(list_hor_lines, xcenter, ycenter,
                                            list_fact)
list_uver_lines = post.unwarp_line_backward(list_ver_lines, xcenter, ycenter,
                                            list_fact)
list_hor_data = post.calc_residual_hor(list_uhor_lines, xcenter, ycenter)
list_ver_data = post.calc_residual_ver(list_uver_lines, xcenter, ycenter)
io.save_residual_plot(
    output_base + "/residual_horizontal_dots_after_BW_correction.png",
    list_hor_data, height, width)
io.save_residual_plot(
    output_base + "/residual_vertical_dots_after_BW_correction.png",
    list_ver_data, height, width)
check1 = post.check_distortion(list_hor_data)
check2 = post.check_distortion(list_ver_data)
if check1 or check2:
    print(
        "!!!Correction of the backward model is not at sub-pixel accuracy!!!")
time_stop = timeit.default_timer()
print("Complete calculation using the backward model in {} second".format(
    time_stop - time_start))

# -----------------------------------------------------------------------------
# Calculate distortion coefficients of a forward model
# -----------------------------------------------------------------------------
time_start = timeit.default_timer()
list_fact = proc.calc_coef_forward(
    list_hor_lines, list_ver_lines, xcenter, ycenter, num_coef)

# Apply distortion correction using nearest interpolation. Note that there's
# vacant pixel problem if the distortion is of the barrel type.
corrected_mat = post.unwarp_image_forward(mat0, xcenter, ycenter, list_fact)
io.save_image(output_base + "/corrected_image_fw.tif", corrected_mat)
io.save_image(output_base + "/diff_corrected_image_fw.tif",
              np.abs(corrected_mat - mat0))
io.save_metadata_txt(output_base + "coefficients_fw.txt", xcenter, ycenter,
                     list_fact)

# Check the correction results
list_uhor_lines = post.unwarp_line_forward(list_hor_lines, xcenter, ycenter,
                                           list_fact)
list_uver_lines = post.unwarp_line_forward(list_ver_lines, xcenter, ycenter,
                                           list_fact)
io.save_plot_image(output_base + "/horizontal_dots_unwarped.png",
                   list_uhor_lines, height, width)
io.save_plot_image(output_base + "/vertical_dots_unwarped.png",
                   list_uver_lines, height, width)
list_hor_data = post.calc_residual_hor(list_uhor_lines, xcenter, ycenter)
list_ver_data = post.calc_residual_ver(list_uver_lines, xcenter, ycenter)
io.save_residual_plot(
    output_base + "/residual_horizontal_dots_after_FW_correction.png",
    list_hor_data, height, width)
io.save_residual_plot(
    output_base + "/residual_vertical_dots_after_FW_correction.png",
    list_ver_data, height, width)
check1 = post.check_distortion(list_hor_data)
check2 = post.check_distortion(list_ver_data)
if check1 or check2:
    print(
        "!!!Correction of the forward model is not at sub-pixel accuracy!!!")
time_stop = timeit.default_timer()
print("Complete calculation using the forward model in {} second".format(
    time_stop - time_start))

# -----------------------------------------------------------------------------
# Calculate distortion coefficients using the backward-from_forward model
# -----------------------------------------------------------------------------
time_start = timeit.default_timer()
list_ffact, list_bfact = proc.calc_coef_backward_from_forward(
    list_hor_lines, list_ver_lines, xcenter, ycenter, num_coef)

# Apply distortion correction
corrected_mat = post.unwarp_image_backward(
    mat0, xcenter, ycenter, list_bfact)
io.save_image(output_base + "/corrected_image_bwfw.tif", corrected_mat)
io.save_image(output_base + "/diff_corrected_image_bwfw.tif",
              np.abs(corrected_mat - mat0))
io.save_metadata_txt(
    output_base + "/coefficients_bwfw.txt", xcenter, ycenter, list_bfact)
# Check the correction results
list_uhor_lines = post.unwarp_line_backward(
    list_hor_lines, xcenter, ycenter, list_bfact)
list_uver_lines = post.unwarp_line_backward(
    list_ver_lines, xcenter, ycenter, list_bfact)
list_hor_data = post.calc_residual_hor(list_uhor_lines, xcenter, ycenter)
list_ver_data = post.calc_residual_ver(list_uver_lines, xcenter, ycenter)
io.save_residual_plot(
    output_base + "/residual_horizontal_dots_after_BWFW_correction.png",
    list_hor_data, height, width)
io.save_residual_plot(
    output_base + "/residual_vertical_dots_after_BWFW_correction.png",
    list_ver_data, height, width)
check1 = post.check_distortion(list_hor_data)
check2 = post.check_distortion(list_ver_data)
if check1 or check2:
    print("!!! Correction of the backward-from-forward model is not at "
          "sub-pixel accuracy !!!")
time_stop = timeit.default_timer()
print("Complete calculation using the backward-from-forward model in {}"
       " second".format(time_stop - time_start))
