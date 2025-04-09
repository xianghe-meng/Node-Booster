# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

import numpy as np
import hashlib


def reverseengineer_curvemapping_to_bezsegs(curve) -> np.ndarray:
    """
    Convert a Blender CurveMapping object to a NumPy array of Bézier segments,
    calculating handle positions based on Blender's internal C functions,
    optionally ensuring X-monotonicity.
    Returns: np.ndarray: An (N-1) x 8 NumPy array [P0x, P0y, P1x, P1y, P2x, P2y, P3x, P3y].
    """

    # NOTE
    # a blender curvemapping bezier has a lot of logic to it with the handles.
    # this function tries to reverse engineer that logic into a list of cubic beziers segments.
    # it's AI generated slop from gemini 2.5, far from perfect, could be largly improved and cleaned up.

    def _guess_handles(current_pt, prev_pt, next_pt):
        """Calculates handle positions mimicking Blender C function calchandle_curvemap."""

        handle_type = current_pt.handle_type
        h1_type = handle_type
        h2_type = handle_type

        p2 = np.array(current_pt.location, dtype=float)

        if (prev_pt is None):
            if (next_pt is None):
                p1 = p2.copy(); p3 = p2.copy()
            else:
                p3 = np.array(next_pt.location, dtype=float)
                p1 = 2.0 * p2 - p3
        else:
            p1 = np.array(prev_pt.location, dtype=float)
            if (next_pt is None):
                p3 = 2.0 * p2 - p1
            else:
                p3 = np.array(next_pt.location, dtype=float)

        dvec_a = np.subtract(p2, p1)
        dvec_b = np.subtract(p3, p2)
        len_a = np.linalg.norm(dvec_a)
        len_b = np.linalg.norm(dvec_b)

        if (abs(len_a) < 1e-5): len_a = 1.0
        if (abs(len_b) < 1e-5): len_b = 1.0

        h1_calc = p2.copy()
        h2_calc = p2.copy()

        if ((h1_type == 'AUTO') or (h1_type == 'AUTO_CLAMPED')):
            tvec = (dvec_b / len_b) + (dvec_a / len_a)
            len_tvec = np.linalg.norm(tvec)
            len_factor = len_tvec * 2.5614

            if (abs(len_factor) > 1e-5):
                scale_a = len_a / len_factor
                scale_b = len_b / len_factor
                base_h1 = p2 - tvec * scale_a
                base_h2 = p2 + tvec * scale_b
                h1_calc = base_h1.copy()
                h2_calc = base_h2.copy()

                if ((h1_type == 'AUTO_CLAMPED') and (prev_pt is not None) and (next_pt is not None)):
                    y_prev = prev_pt.location[1]
                    y_curr = current_pt.location[1]
                    y_next = next_pt.location[1]
                    ydiff1 = y_prev - y_curr
                    ydiff2 = y_next - y_curr
                    is_extremum = (ydiff1 <= 0.0 and ydiff2 <= 0.0) or \
                                  (ydiff1 >= 0.0 and ydiff2 >= 0.0)
                    if (is_extremum):
                        h1_calc[1] = y_curr
                    else:
                        if ydiff1 <= 0.0: h1_calc[1] = max(y_prev, base_h1[1])
                        else: h1_calc[1] = min(y_prev, base_h1[1])

                if ((h2_type == 'AUTO_CLAMPED') and (prev_pt is not None) and (next_pt is not None)):
                    y_prev = prev_pt.location[1]
                    y_curr = current_pt.location[1]
                    y_next = next_pt.location[1]
                    ydiff1 = y_prev - y_curr
                    ydiff2 = y_next - y_curr
                    is_extremum = (ydiff1 <= 0.0 and ydiff2 <= 0.0) or \
                                  (ydiff1 >= 0.0 and ydiff2 >= 0.0)
                    if (is_extremum):
                        h2_calc[1] = y_curr
                    else:
                        if (ydiff1 <= 0.0): h2_calc[1] = min(y_next, base_h2[1])
                        else: h2_calc[1] = max(y_next, base_h2[1])

        elif (h1_type == 'VECTOR'):
            h1_calc = p2 - dvec_a / 3.0
            h2_calc = p2 + dvec_b / 3.0

        if np.any(np.isnan(h1_calc)): h1_calc = p2.copy()
        if np.any(np.isnan(h2_calc)): h2_calc = p2.copy()

        return h1_calc, h2_calc

    def _points_x_monotonicity(points, all_left_h, all_right_h):
        """
        Adjusts calculated handle X-coordinates to ensure X-monotonicity for each segment.
        Enforces x0 <= x1 <= x2 <= x3 where P1=HR_i, P2=HL_i+1.

        Args:
            points: List of CurveMapPoint objects.
            all_left_h: List of calculated left handle positions (np.arrays).
            all_right_h: List of calculated right handle positions (np.arrays).

        Returns:
            tuple: (final_left_h, final_right_h) - Lists of adjusted handle positions.
        """
        n_points = len(points)
        if (n_points < 2):
            return list(all_left_h), list(all_right_h)

        # Create copies to modify
        final_left_h = [h.copy() for h in all_left_h]
        final_right_h = [h.copy() for h in all_right_h]

        # Iterate through segments [i, i+1]
        for i in range(n_points - 1):
            # P0 = knot[i], P1 = HR[i], P2 = HL[i+1], P3 = knot[i+1]
            x_k_i = points[i].location[0]
            x_k_i1 = points[i+1].location[0]
            # X-coords of handles relevant to this segment
            x_hr_i_orig = final_right_h[i][0]   # P1.x original
            x_hl_i1_orig = final_left_h[i+1][0] # P2.x original

            # Apply clamping based on x0 <= x1 <= x2 <= x3
            # 1. Clamp P1.x (x_hr_i) >= P0.x (x_k_i)
            x_hr_i_clamped = max(x_k_i, x_hr_i_orig)
            # 2. Clamp P2.x (x_hl_i1) <= P3.x (x_k_i1)
            x_hl_i1_clamped = min(x_k_i1, x_hl_i1_orig)
            # 3. Check for crossover: P1.x > P2.x after clamping
            if x_hr_i_clamped > x_hl_i1_clamped:
                # Crossover occurred. Handles need to meet.
                # Calculate the midpoint of the conflicting interval.
                x_split = (x_hr_i_clamped + x_hl_i1_clamped) / 2.0
                # Ensure the split point is strictly within the knot interval.
                x_split = max(x_k_i, min(x_k_i1, x_split))
                # Set both handles' X to the split point.
                final_right_h[i][0] = x_split
                final_left_h[i+1][0] = x_split
            else:
                # No crossover, just apply the individual clamps.
                final_right_h[i][0] = x_hr_i_clamped
                final_left_h[i+1][0] = x_hl_i1_clamped
            continue

        return final_left_h, final_right_h

    points = curve.points
    n_points = len(points)

    if (n_points < 2):
        return np.empty((0, 8), dtype=float)

    # Calculate initial handle positions
    all_left_h = [np.zeros(2) for _ in range(n_points)]
    all_right_h = [np.zeros(2) for _ in range(n_points)]

    for i in range(n_points):
        current_pt = points[i]
        prev_pt = points[i - 1] if i > 0 else None
        next_pt = points[i + 1] if i < n_points - 1 else None

        left_h, right_h = _guess_handles(current_pt, prev_pt, next_pt)
        all_left_h[i] = left_h
        all_right_h[i] = right_h
        continue

    # Apply Endpoint Handle Correction (if applicable)
    # This is a simplified version, adjust if needed for specific handle types/logic
    if (n_points > 2):
        if (points[0].handle_type == 'AUTO'):
            P0 = np.array(points[0].location, dtype=float)
            P1_orig = all_right_h[0]
            hlen = np.linalg.norm(np.subtract(P0, P1_orig)) #
            if (hlen > 1e-7):
                neighbor_handle = all_left_h[1]
                clamped_neighbor_x = max(neighbor_handle[0], P0[0])
                direction_vec = np.array([clamped_neighbor_x - P0[0], neighbor_handle[1] - P0[1]])
                nlen = np.linalg.norm(direction_vec)
                if (nlen > 1e-7):
                    scaled_direction = direction_vec * (hlen / nlen)
                    all_right_h[0] = P0 + scaled_direction

        last_idx = n_points - 1
        if (points[last_idx].handle_type == 'AUTO'):
            P3 = np.array(points[last_idx].location, dtype=float)
            P2_orig = all_left_h[last_idx]
            hlen = np.linalg.norm(np.subtract(P3, P2_orig)) #
            if (hlen > 1e-7):
                neighbor_handle = all_right_h[last_idx - 1]
                clamped_neighbor_x = min(neighbor_handle[0], P3[0])
                direction_vec = np.array([clamped_neighbor_x - P3[0], neighbor_handle[1] - P3[1]])
                nlen = np.linalg.norm(direction_vec)
                if (nlen > 1e-7):
                    scaled_direction = direction_vec * (hlen / nlen)
                    all_left_h[last_idx] = P3 + scaled_direction

    # Apply X-Monotonicity
    final_left_h, final_right_h = _points_x_monotonicity(points, all_left_h, all_right_h)

    # Build segments
    segments_list = []
    for i in range(n_points - 1):

        P0 = np.array(points[i].location, dtype=float)
        P3 = np.array(points[i + 1].location, dtype=float)

        P1 = final_right_h[i]
        P2 = final_left_h[i + 1]

        if (np.any(np.isnan(P0)) or np.any(np.isnan(P1)) or \
            np.any(np.isnan(P2)) or np.any(np.isnan(P3))):
            print(f"Warning: NaN detected in segment {i}. Skipping.")
            continue

        segment_row = np.concatenate((P0, P1, P2, P3))
        segments_list.append(segment_row)
        continue

    if (not segments_list):
         return np.empty((0, 8), dtype=float)

    segments_array = np.array(segments_list, dtype=float)
    
    return segments_array


def is_handles_aligned(handle, anchor1, anchor2, epsilon:float=1e-6) -> bool:
    """Checks if the handle vector (anchor1 -> handle) is collinear with the
    anchor vector (anchor1 -> anchor2)."""

    V_handle = handle - anchor1
    V_anchor = anchor2 - anchor1

    # Check if handle vector has zero length (squared magnitude)
    mag_handle_sq = np.dot(V_handle, V_handle)
    if (mag_handle_sq < epsilon * epsilon):
        return True # Zero length handle is considered aligned (VECTOR)

    # Check if anchor vector has zero length (squared magnitude)
    mag_anchor_sq = np.dot(V_anchor, V_anchor)
    if (mag_anchor_sq < epsilon * epsilon):
        return False # Cannot align with a zero-length anchor segment

    # Calculate the 2D cross product's Z component
    # If vectors are A=(ax, ay) and B=(bx, by), cross_product = ax*by - ay*bx
    cross_product = (V_handle[0] * V_anchor[1]) - (V_handle[1] * V_anchor[0])

    # Return True if the cross product is close to zero (collinear)
    return (abs(cross_product) < epsilon)


def bezsegs_to_curvemapping(curve, segments:np.ndarray) -> None:
    """Apply an N x 8 NumPy array of Bézier segments to a blender curvemapping.
    Assumes `segments` is a NumPy array where each row is: [P0x, P0y, P1x, P1y, P2x, P2y, P3x, P3y]
    """

    if (not isinstance(segments, np.ndarray)):
        raise ValueError("Input segments must be a NumPy array")
    if ((segments.ndim != 2) or (segments.shape[1] != 8)):
        raise ValueError(f"Input segments array must have shape (N, 8), got {segments.shape}")

    num_segments = segments.shape[0]
    if (num_segments == 0):
        raise ValueError("Input segments array is empty")

    num_points = num_segments + 1
    reset_curvemapping(curve) # Start fresh with default 2 points

    # Ensure enough points exist in the Blender curve
    while (len(curve.points) < num_points):
        curve.points.new(0, 0) 

    # Set first point's location
    P0_first = segments[0, 0:2] # First point of first segment
    curve.points[0].location = tuple(P0_first) # Convert slice to tuple for location

    # Set subsequent points and handle types based on segments
    for i in range(num_segments):
        try:
            # Extract points directly using slicing
            P0 = segments[i, 0:2]
            P1 = segments[i, 2:4]
            P2 = segments[i, 4:6]
            P3 = segments[i, 6:8]

            # Set Point Locations
            # Location of the end point of this segment corresponds to curve.points[i+1]
            curve.points[i+1].location = tuple(P3) # Convert slice to tuple

            # vector handle types are simply aligned handles/anchors.
            # default are all auto handles. We ignore clamped handles. too similar with auto imo.
            if ((curve.points[i].handle_type == "AUTO") \
                and is_handles_aligned(P1, P0, P3)):
                curve.points[i].handle_type = "VECTOR"
            if ((curve.points[i+1].handle_type == "AUTO") \
                and is_handles_aligned(P2, P3, P0)):
                curve.points[i+1].handle_type = "VECTOR"
            continue

        except Exception as e:
            print(f"WARNING: Unexpected error processing segment {i}: {e}")
            print(f"Segment data (row): {segments[i]}")

        continue

    return None


def reset_curvemapping(curve) -> None:
    """clear all points of this curve (2 pts need to be left)"""

    points = curve.points

    while (len(curve.points)>2):
        points.remove(points[1])

    points[0].location = (0,0)
    points[1].location = (1,1)

    return None


def hash_bezsegs(segments:np.ndarray)->str:
    """Generate a string hash value for a numpy array containing bezier curve data.
    segments (np.ndarray): An (N-1) x 8 NumPy array [P0x, P0y, P1x, P1y, P2x, P2y, P3x, P3y]."""

    if (segments is None) \
        or (not isinstance(segments, np.ndarray)) \
        or (segments.ndim != 2) \
        or (segments.shape[1] != 8):
        return None

    # Convert to bytes and hash
    return hashlib.md5(segments.tobytes()).hexdigest()


def ensure_bezsegs_monotonic(segments:np.ndarray)->np.ndarray:
    """Ensure the segments represent a curve monotonic in x.
    This involves sorting anchor points by x-coordinate and then adjusting handles.
    Monotonicity is important for interpolation, preventing the curve from backtracking on the X axis.
    segments (np.ndarray): An (N) x 8 NumPy array [P0x, P0y, P1x, P1y, P2x, P2y, P3x, P3y].
    Returns a *new* NumPy array with the sorted and adjusted segments.
    """

    if (segments is None) or (segments.size == 0):
        return np.empty((0, 8), dtype=segments.dtype if segments is not None else float) # Return empty array

    num_segments = segments.shape[0]
    num_points = num_segments + 1

    # 1. Deconstruct into anchor points and handles
    #    anchor_handle_data format: [Ax, Ay, HLx, HLy, HRx, HRy]
    anchor_handle_data = np.zeros((num_points, 6), dtype=segments.dtype)

    # Fill Anchor locations (Ax, Ay)
    anchor_handle_data[0, 0:2] = segments[0, 0:2]  # First anchor is P0 of first segment
    anchor_handle_data[1:, 0:2] = segments[:, 6:8] # Subsequent anchors are P3 of each segment

    # Fill Left Handles (HLx, HLy)
    # First anchor's left handle defaults to its own location
    anchor_handle_data[0, 2:4] = anchor_handle_data[0, 0:2]
    # Other left handles are P2 of the preceding segment
    anchor_handle_data[1:, 2:4] = segments[:, 4:6]

    # Fill Right Handles (HRx, HRy)
    # Intermediate right handles are P1 of the current segment
    anchor_handle_data[:-1, 4:6] = segments[:, 2:4]
    # Last anchor's right handle defaults to its own location
    anchor_handle_data[-1, 4:6] = anchor_handle_data[-1, 0:2]

    # 2. Sort by Anchor X-coordinate
    sort_indices = np.argsort(anchor_handle_data[:, 0])
    sorted_anchor_handle_data = anchor_handle_data[sort_indices]

    # 3. Reconstruct segments from sorted data
    # Create a new array for the sorted segments
    sorted_segments = np.zeros((num_segments, 8), dtype=segments.dtype)

    # P0 comes from anchor i's location
    sorted_segments[:, 0:2] = sorted_anchor_handle_data[:-1, 0:2]
    # P1 comes from anchor i's right handle
    sorted_segments[:, 2:4] = sorted_anchor_handle_data[:-1, 4:6]
    # P2 comes from anchor i+1's left handle
    sorted_segments[:, 4:6] = sorted_anchor_handle_data[1:, 2:4]
    # P3 comes from anchor i+1's location
    sorted_segments[:, 6:8] = sorted_anchor_handle_data[1:, 0:2]

    # 4. Apply handle clamping to the *newly reconstructed* segments
    #    (This is the same vectorized logic as before)
    x0 = sorted_segments[:, 0]
    x1 = sorted_segments[:, 2]
    x2 = sorted_segments[:, 4]
    x3 = sorted_segments[:, 6]

    x_min = np.minimum(x0, x3)
    x_max = np.maximum(x0, x3)

    x1_clamped = np.clip(x1, x_min, x_max)
    x2_clamped = np.clip(x2, x_min, x_max)

    crossover_mask = x1_clamped > x2_clamped
    x_split = (x1_clamped + x2_clamped) / 2.0

    sorted_segments[:, 2] = np.where(crossover_mask, x_split, x1_clamped)
    sorted_segments[:, 4] = np.where(crossover_mask, x_split, x2_clamped)

    return sorted_segments


# def evaluate_cubic_bezseg(segment:np.ndarray, t:float):
#     """
#     Evaluate a cubic Bézier segment at parameter t.
#     evaluate segment as (np.ndarray): An (N-1) x 8 NumPy array [P0x, P0y, P1x, P1y, P2x, P2y, P3x, P3y]
#     """
#     # Ensure segment is a numpy array
#     try:
#         # Extract points
#         segment_arr = np.asarray(segment)
#         if segment_arr.shape != (8,):
#             raise ValueError(f"Expected segment shape (8,), got {segment_arr.shape}")
#         P0 = segment_arr[0:2]
#         P1 = segment_arr[2:4]
#         P2 = segment_arr[4:6]
#         P3 = segment_arr[6:8]

#     except (ValueError, TypeError) as e:
#         print(f"Error processing segment data in evaluate: {e}")
#         print(f"Segment data: {segment}")
#         return np.array([0.0, 0.0]) # Fallback

#     # Calculate point on curve
#     omt = 1.0 - t
#     omt2 = omt * omt
#     omt3 = omt2 * omt
#     t2 = t * t
#     t3 = t2 * t

#     return (P0 * omt3) + (P1 * 3.0 * omt2 * t) + (P2 * 3.0 * omt * t2) + (P3 * t3)


def sample_bezsegs(segments: np.ndarray, sampling_rate: int):
    """Generate points from the segments numpy array using vectorized operations.
    segments (np.ndarray): An (N) x 8 NumPy array [P0x, P0y, P1x, P1y, P2x, P2y, P3x, P3y].
    sampling_rate (int): Number of steps *between* points per segment (e.g., 1 gives start/end, 2 gives start/mid/end).
    Returns a NumPy array of shape (N * sampling_rate + 1, 2) with the calculated points.
    """

    if segments is None or segments.size == 0:
        return np.empty((0, 2), dtype=segments.dtype if segments is not None else float)
    if sampling_rate < 1:
        raise ValueError("sampling_rate must be at least 1")

    num_segments = segments.shape[0]
    num_points_per_segment = sampling_rate + 1

    # Extract control points for all segments
    # Reshape to (num_segments, 4, 2) for easier access
    control_points = segments.reshape(num_segments, 4, 2)
    P0 = control_points[:, 0, :][:, np.newaxis, :] # Shape (N, 1, 2)
    P1 = control_points[:, 1, :][:, np.newaxis, :] # Shape (N, 1, 2)
    P2 = control_points[:, 2, :][:, np.newaxis, :] # Shape (N, 1, 2)
    P3 = control_points[:, 3, :][:, np.newaxis, :] # Shape (N, 1, 2)

    # Generate t values (parameterization)
    # Shape (1, num_points_per_segment, 1) to broadcast correctly with points
    t = np.linspace(0, 1, num_points_per_segment).reshape(1, num_points_per_segment, 1)

    # Calculate powers of t and (1-t)
    omt = 1.0 - t
    omt2 = omt * omt
    omt3 = omt2 * omt
    t2 = t * t
    t3 = t2 * t

    # Calculate points using the Bezier formula with broadcasting
    # Result shape: (num_segments, num_points_per_segment, 2)
    points = (P0 * omt3) + (P1 * 3.0 * omt2 * t) + (P2 * 3.0 * omt * t2) + (P3 * t3)

    # Reshape to a 2D array: (num_segments * num_points_per_segment, 2)
    all_points = points.reshape(-1, 2)

    # Remove duplicate points at segment junctions
    # Keep the first point (t=0) of the first segment.
    # Keep points from t=1/sampling_rate to t=1 for all segments.
    # Create indices to keep: 0 (start of first seg), and then 1 to sampling_rate+1 for each segment
    indices_to_keep = [0] # Keep the very first point
    for i in range(num_segments):
        start = i * num_points_per_segment + 1
        end = start + sampling_rate # +1 for num_points, -1 because index starts at 1
        indices_to_keep.extend(range(start, end + 1))

    # Ensure indices are within bounds (handles cases like sampling_rate=1 correctly)
    indices_to_keep = [idx for idx in indices_to_keep if idx < all_points.shape[0]]
    sampled_points = all_points[indices_to_keep]

    return sampled_points


def sample_bezsegs_with_t(segments: np.ndarray, sampling_rate: int):
    """Generate points and their corresponding t-values per segment using vectorized operations.
    Args:
        segments (np.ndarray): An (N) x 8 NumPy array [P0x, P0y, P1x, P1y, P2x, P2y, P3x, P3y].
        sampling_rate (int): Number of steps *between* points per segment (e.g., 1 gives start/end, 2 gives start/mid/end).
                             Results in sampling_rate + 1 points per segment.

    Returns:
        tuple[list[np.ndarray], list[np.ndarray]]:
            - points_per_segment: List where each element is a NumPy array (sampling_rate + 1, 2)
                                   containing the calculated points for one segment.
            - t_values_per_segment: List where each element is a NumPy array (sampling_rate + 1,)
                                     containing the t-values corresponding to the points in the
                                     points_per_segment list at the same index.
    """

    if segments is None or segments.size == 0:
        return [], [] # Return empty lists
    if sampling_rate < 1:
        raise ValueError("sampling_rate must be at least 1")

    num_segments = segments.shape[0]
    num_points_per_segment = sampling_rate + 1
    original_dtype = segments.dtype

    # Extract control points for all segments
    control_points = segments.reshape(num_segments, 4, 2)
    P0 = control_points[:, 0, :][:, np.newaxis, :] # Shape (N, 1, 2)
    P1 = control_points[:, 1, :][:, np.newaxis, :] # Shape (N, 1, 2)
    P2 = control_points[:, 2, :][:, np.newaxis, :] # Shape (N, 1, 2)
    P3 = control_points[:, 3, :][:, np.newaxis, :] # Shape (N, 1, 2)

    # Generate t values (parameterization)
    t_1d = np.linspace(0, 1, num_points_per_segment, dtype=np.float64) # Use float64 for precision
    # Reshape for broadcasting calculation
    t = t_1d.reshape(1, num_points_per_segment, 1)

    # Calculate powers of t and (1-t)
    omt = 1.0 - t
    omt2 = omt * omt
    omt3 = omt2 * omt
    t2 = t * t
    t3 = t2 * t

    # Calculate points using the Bezier formula with broadcasting
    # Result shape: (num_segments, num_points_per_segment, 2)
    # Ensure calculation uses float64, then potentially cast back if needed
    points = (P0.astype(np.float64) * omt3) + \
             (P1.astype(np.float64) * 3.0 * omt2 * t) + \
             (P2.astype(np.float64) * 3.0 * omt * t2) + \
             (P3.astype(np.float64) * t3)
    
    # Convert result back to original dtype if it was float32 or similar
    if original_dtype != np.float64:
        points = points.astype(original_dtype)

    # Populate lists using list comprehensions
    # points_per_segment will be a list of (num_points_per_segment, 2) arrays
    points_per_segment = [points[i] for i in range(num_segments)]
    # t_values_per_segment will be a list of (num_points_per_segment,) arrays (all identical)
    t_values_per_segment = [t_1d for _ in range(num_segments)]

    return points_per_segment, t_values_per_segment


def casteljau_subdiv_bezsegs(segments:np.ndarray, t_values:np.ndarray, tol:float=1e-6):
    """
    Batch subdivide Bézier segments and return a combined array.
    Subdivides segments where the corresponding t_value is between tol and 1-tol.
    Segments not subdivided are kept as is.
    Args:
        segments (np.ndarray): An (N, 8) NumPy array of Bézier segments
                               [P0x, P0y, P1x, P1y, P2x, P2y, P3x, P3y].
        t_values (np.ndarray): An (N,) NumPy array of parameter values (0.0 to 1.0)
                                corresponding to each segment for subdivision.
        tol (float): Tolerance to treat t-values near 0 or 1 as non-subdividing.
    Returns:
        np.ndarray: A new NumPy array containing all resulting segments.
    """

    # --- Input Validation ---
    if not isinstance(segments, np.ndarray) or segments.ndim != 2 or segments.shape[1] != 8:
        raise ValueError(f"Input segments must be an (N, 8) NumPy array, got shape {segments.shape}")
    num_segments = segments.shape[0]
    if not isinstance(t_values, np.ndarray) or t_values.shape != (num_segments,):
        raise ValueError(f"Input t_values must be an (N,) NumPy array, got shape {t_values.shape}")
    if num_segments == 0:
        return np.empty((0, 8), dtype=segments.dtype)

    # --- Perform Vectorized Calculation (same as before) ---
    t = np.clip(t_values, 0.0, 1.0).reshape(-1, 1)
    omt = 1.0 - t
    control_points = segments.reshape(num_segments, 4, 2)
    P0, P1, P2, P3 = control_points[:, 0, :], control_points[:, 1, :], control_points[:, 2, :], control_points[:, 3, :]
    Q0 = P0 * omt + P1 * t
    Q1 = P1 * omt + P2 * t
    Q2 = P2 * omt + P3 * t
    R0 = Q0 * omt + Q1 * t
    R1 = Q1 * omt + Q2 * t
    S = R0 * omt + R1 * t

    # --- Construct Potential Sub-segments ---
    # These arrays hold the potential results IF subdivision happens
    potential_seg1 = np.concatenate((P0, Q0, R0, S), axis=1)
    potential_seg2 = np.concatenate((S, R1, Q2, P3), axis=1)

    # --- Identify Segments to Subdivide ---
    subdivide_mask = (t_values > tol) & (t_values < 1.0 - tol) # Use original t_values for mask

    # --- Assemble the Output Array ---
    output_segments_list = []
    for i in range(num_segments):
        if subdivide_mask[i]:
            output_segments_list.append(potential_seg1[i])
            output_segments_list.append(potential_seg2[i])
        else:
            output_segments_list.append(segments[i])

    if (not output_segments_list):
        return np.empty((0, 8), dtype=segments.dtype)

    # Determine appropriate dtype (original or float if potential_seg2 was involved)
    result_dtype = np.promote_types(segments.dtype, potential_seg2.dtype)
    return np.array(output_segments_list, dtype=result_dtype)


def cut_bezsegs(segments:np.ndarray, xlocation:float, sampling_rate:int=50, tolerance=1e-6,):
    """
    Subdivides Bézier segments at a given x-location by estimating the subdivision
    parameter 't' from pre-sampled points.
    Args:
        segments (np.ndarray): An (N, 8) NumPy array of Bézier segments
                               [P0x, P0y, P1x, P1y, P2x, P2y, P3x, P3y].
        xlocation (float): The target x-coordinate for subdivision.
        sampling_rate (int): The density used by sample_bezsegs_with_t to
                             generate points for estimating 't'. Higher values
                             increase accuracy but cost more computation upfront.
    Returns:
        np.ndarray: A new NumPy array containing all resulting segments after
                    subdivision. Shape will be (M, 8) where N <= M <= 2*N.
                    Returns the original array if no subdivisions occur.
    """

    if segments is None or segments.size == 0:
        return np.empty((0, 8), dtype=segments.dtype if segments is not None else float)
    if sampling_rate < 1:
        raise ValueError("sampling_rate must be at least 1")

    num_segments = segments.shape[0]

    # 1. Sample points and t-values for estimation
    try:
        points_per_segment, t_values_per_segment = sample_bezsegs_with_t(segments, sampling_rate)
    except Exception as e:
        print(f"Error during sampling in cut_bezsegs: {e}")
        return segments.copy()

    if len(points_per_segment) != num_segments or len(t_values_per_segment) != num_segments:
        print(f"Warning: Mismatch between segment count and sampling results. Returning original.")
        return segments.copy()

    # 2. Initialize the t-map for subdivision
    t_map = np.zeros(num_segments, dtype=np.float64)
    subdivide_mask = np.zeros(num_segments, dtype=bool) # Track which segments to subdivide

    # 3. Loop through segments to find estimated t-values
    for i in range(num_segments):
        P0x = segments[i, 0]
        P3x = segments[i, 6]
        is_within = (P0x < xlocation < P3x) or (P3x < xlocation < P0x)

        if is_within:
            sampled_pts = points_per_segment[i]
            sampled_ts = t_values_per_segment[i]
            if sampled_pts.size == 0 or sampled_ts.size == 0: continue

            try:
                idx = np.argmin(np.abs(sampled_pts[:, 0] - xlocation))
                estimated_t = sampled_ts[idx]
                # Only mark for subdivision if estimated t is not too close to ends
                if tolerance < estimated_t < 1.0 - tolerance:
                     t_map[i] = estimated_t
                     subdivide_mask[i] = True
                # else: leave t_map[i] as 0.0, subdivide_mask[i] as False
            except Exception as e:
                print(f"Warning: Error finding nearest t for segment {i}: {e}. Skipping.")

    # 4. Call the batch subdivision function
    try:
        # Use the t_map where subdivision is needed, otherwise t=0 (no split)
        subdivided_segments = casteljau_subdiv_bezsegs(segments, t_map, tol=tolerance)
    except Exception as e:
        print(f"Error during batch subdivision in cut_bezsegs: {e}")
        return segments.copy()

    # 5. Adjust x-coordinate of the new anchor points
    # Ensure we modify a float array copy
    modified_segments = subdivided_segments.astype(float, copy=True)
    output_idx = 0
    for i in range(num_segments):
        if subdivide_mask[i]: # Check if this original segment *was* actually split
            # Adjust P3x of first child segment
            modified_segments[output_idx, 6] = xlocation
            # Adjust P0x of second child segment
            modified_segments[output_idx + 1, 0] = xlocation
            # Move output index past the two children
            output_idx += 2
        else:
            # Move output index past the single original segment
            output_idx += 1

    return modified_segments


# def casteljau_subdiv_bezseg(segment_arr: np.ndarray, t: float | None = None, xloc: float | None = None, tol: float = 1e-6):
#     """
#     Subdivide a cubic Bézier segment using De Casteljau's algorithm.

#     Can subdivide either at a specific parameter `t` or at a specific x-location `xloc`.
#     If `t` is provided, it takes precedence.
#     If only `xloc` is provided, the cubic equation for x(t) = xloc is solved to find `t`.

#     Args:
#         segment_arr (np.ndarray): An 8-element NumPy array [P0x, P0y, P1x, P1y, P2x, P2y, P3x, P3y].
#         t (float | None): The parameter (0.0 to 1.0) for subdivision. Defaults to None.
#         xloc (float | None): The target x-coordinate for subdivision. Used if t is None. Defaults to None.
#         tol (float): Tolerance used for comparing t values to 0 and 1 and for filtering roots.

#     Returns:
#         tuple[np.ndarray, np.ndarray | None]: 
#             - (seg1_arr, seg2_arr) if subdivision occurs.
#             - (original_segment_arr, None) if subdivision does not occur.
#     """
#     try:
#         # --- Input Validation and Parameter Determination --- 
#         if not isinstance(segment_arr, np.ndarray) or segment_arr.shape != (8,):
#             raise ValueError(f"Expected segment_arr shape (8,), got {segment_arr.shape}")

#         P0x, P1x, P2x, P3x = segment_arr[0], segment_arr[2], segment_arr[4], segment_arr[6]
#         final_t = -1.0 # Sentinel for t not yet determined

#         if t is not None:
#             final_t = np.clip(float(t), 0.0, 1.0)
#         elif xloc is not None:
#             # Check endpoints first (within tolerance)
#             if abs(xloc - P0x) < tol:
#                 final_t = 0.0
#             elif abs(xloc - P3x) < tol:
#                 final_t = 1.0
#             else:
#                 # --- Solve the cubic equation x(t) - xloc = 0 --- 
#                 # Coefficients of the cubic polynomial in t: At^3 + Bt^2 + Ct + D = 0
#                 # Where x(t) = (1-t)^3*P0x + 3(1-t)^2*t*P1x + 3(1-t)*t^2*P2x + t^3*P3x
#                 # Rearranging x(t) - xloc = 0 gives:
#                 A = P3x - 3*P2x + 3*P1x - P0x
#                 B = 3*P2x - 6*P1x + 3*P0x
#                 C = 3*P1x - 3*P0x
#                 D = P0x - xloc

#                 # Find the roots using numpy
#                 # Note: np.roots expects coefficients from highest power to lowest
#                 # Handle the near-zero coefficient case for A (reduces to quadratic/linear)
#                 if abs(A) < tol:
#                     if abs(B) < tol: # Linear case: Ct + D = 0
#                         if abs(C) > tol:
#                             roots = [-D / C]
#                         else: # Constant case D = 0 (means xloc = P0x, handled above)
#                             roots = [] 
#                     else: # Quadratic case: Bt^2 + Ct + D = 0
#                          roots = np.roots([B, C, D])
#                 else: # Cubic case: At^3 + Bt^2 + Ct + D = 0
#                      roots = np.roots([A, B, C, D])

#                 # Filter roots: keep only real roots within [0 - tol, 1 + tol]
#                 valid_roots = []
#                 for r in roots:
#                     if abs(np.imag(r)) < tol: # Check if root is real (within tolerance)
#                          real_r = np.real(r)
#                          if (0.0 - tol) <= real_r <= (1.0 + tol):
#                              valid_roots.append(np.clip(real_r, 0.0, 1.0)) # Clip to exact [0,1]
                
#                 if len(valid_roots) == 1:
#                     final_t = valid_roots[0]
#                 elif len(valid_roots) > 1:
#                     # Multiple valid roots means curve crosses xloc multiple times.
#                     # Defaulting to the smallest valid t (first crossing from P0).
#                     final_t = min(valid_roots)
#                     # print(f"Warning: Multiple valid t values found for xloc={xloc}. Using smallest t={final_t:.4f}.")
#                 # If len(valid_roots) == 0, final_t remains -1.0 (no subdivision)

#         else:
#             raise ValueError("Either t or xloc must be provided for subdivision.")

#         # --- Perform Subdivision if t was determined --- 
#         if final_t >= 0.0:
#             P0, P1, P2, P3 = segment_arr[0:2], segment_arr[2:4], segment_arr[4:6], segment_arr[6:8]
            
#             omt = 1.0 - final_t
#             Q0 = P0 * omt + P1 * final_t
#             Q1 = P1 * omt + P2 * final_t
#             Q2 = P2 * omt + P3 * final_t
#             R0 = Q0 * omt + Q1 * final_t
#             R1 = Q1 * omt + Q2 * final_t
#             S = R0 * omt + R1 * final_t

#             seg1_arr = np.concatenate((P0, Q0, R0, S))
#             seg2_arr = np.concatenate((S, R1, Q2, P3))

#             return seg1_arr, seg2_arr
#         else:
#             # No valid t found or needed, return original segment and None
#             return segment_arr, None

#     except (ValueError, TypeError) as e:
#         print(f"Error processing segment data in casteljau_subdiv_bezseg: {e}")
#         print(f"Input segment_arr: {segment_arr}, t: {t}, xloc: {xloc}")
#         return segment_arr, None # Return original segment and None on error


# def casteljau_subdiv_bezsegs(segments: np.ndarray, xloc: float):
#     """
#     Subdivide segments in a NumPy array where the curve passes through a specific x-location.

#     Calls `casteljau_subdiv_bezseg` for each segment, providing the `xloc`.
#     `casteljau_subdiv_bezseg` handles the logic of checking the range and finding `t`.

#     Args:
#         segments (np.ndarray): An N x 8 NumPy array of Bézier segments.
#         xloc (float): The target x-coordinate for subdivision.

#     Returns:
#         np.ndarray: A new NumPy array containing the original and subdivided segments.
#                     The number of rows may be greater than N if subdivisions occurred.
#     """

#     if (segments is None) or (segments.size == 0):
#         return np.empty((0, 8), dtype=segments.dtype if segments is not None else float)

#     output_segments_list = []
#     original_dtype = segments.dtype # Preserve original dtype

#     for segment_row in segments:
#         try:
#             # Call the modified function, providing only xloc
#             # It returns (seg1, seg2) if split, or (original, None) if not split
#             seg1, seg2_or_none = casteljau_subdiv_bezseg(segment_row, xloc=xloc)

#             # Append the result(s)
#             output_segments_list.append(seg1) # Always append the first returned segment
#             if seg2_or_none is not None:
#                 output_segments_list.append(seg2_or_none) # Append the second if subdivision happened

#         except Exception as e:
#             print(f"Error processing segment during casteljau_subdiv_bezsegs: {e}")
#             # Add the original segment back on error during the call
#             output_segments_list.append(segment_row)
#         continue

#     # Reassemble the segments array 
#     if not output_segments_list:
#          return np.empty((0, 8), dtype=original_dtype)

#     return np.array(output_segments_list, dtype=original_dtype)


# def extended_seg(segment, goal_xy):
#     """
#     Extend a segment so its endpoint P3 becomes goal_xy.
#     Creates a new segment starting from the original P3.
#     Approximates new handles based on the tangent of the original segment.
#     Returns the new segment (P0_new, P1_new, P2_new, P3_new).
#     """
#     try:
#         P0, P1, P2, P3 = [np.array(pt, dtype=float) for pt in segment]
#         goal_xy = np.array(goal_xy, dtype=float)
#     except Exception as e:
#          print(f"Error converting points in extended_seg: {e}")
#          fallback_pt = np.array([0.0, 0.0])
#          return (fallback_pt, fallback_pt, fallback_pt, fallback_pt)
         
#     # Use tangent at the end of the original segment (P3-P2)
#     tangent = P3 - P2 if np.linalg.norm(P3-P2) > 1e-9 else np.array([0.0,0.0]) 
    
#     new_P0 = P3 # New segment starts where old one ended
#     # Estimate new P1 based on the tangent direction
#     new_P1 = P3 + tangent / 3.0 
    
#     new_P3 = goal_xy # New segment ends at the goal
#     # Estimate new P2 based on pulling back from the new end point
#     # Use the vector from the old P3 to the new P3 as a guide
#     vec_P3_newP3 = new_P3 - P3
#     new_P2 = new_P3 - vec_P3_newP3 / 3.0 # Simplistic estimate
    
#     return (new_P0, new_P1, new_P2, new_P3)


# def match_curves(curve1_segs_arr: np.ndarray, curve2_segs_arr: np.ndarray, x_bounds):
#     """
#     Adjust two curves, provided as N x 8 NumPy arrays, so that both have 
#     segment boundaries at the specified x_bounds.
    
#     Args:
#         curve1_segs_arr (np.ndarray): First curve as N1x8 array.
#         curve2_segs_arr (np.ndarray): Second curve as N2x8 array.
#         x_bounds (list): Sorted list of x-coordinates for desired boundaries.

#     Returns:
#         tuple[np.ndarray, np.ndarray]: The adjusted curves as new M1x8 and M2x8 arrays.
#     """
    
#     # --- Input Validation ---
#     if not isinstance(curve1_segs_arr, np.ndarray) or curve1_segs_arr.ndim != 2 or curve1_segs_arr.shape[1] != 8:
#         print(f"Error: curve1_segs_arr must be an Nx8 NumPy array, got shape {curve1_segs_arr.shape if hasattr(curve1_segs_arr, 'shape') else type(curve1_segs_arr)}")
#         return curve1_segs_arr, curve2_segs_arr # Return originals on error
#     if not isinstance(curve2_segs_arr, np.ndarray) or curve2_segs_arr.ndim != 2 or curve2_segs_arr.shape[1] != 8:
#         print(f"Error: curve2_segs_arr must be an Nx8 NumPy array, got shape {curve2_segs_arr.shape if hasattr(curve2_segs_arr, 'shape') else type(curve2_segs_arr)}")
#         return curve1_segs_arr, curve2_segs_arr
#     if not curve1_segs_arr.size or not curve2_segs_arr.size:
#          print("Warning: One or both input curves are empty in match_curves.")
#          return curve1_segs_arr, curve2_segs_arr
#     if not x_bounds:
#          print("Warning: x_bounds is empty in match_curves. Returning original curves.")
#          return curve1_segs_arr, curve2_segs_arr
#     if not all(isinstance(x, (int, float)) for x in x_bounds):
#             print("Error: x_bounds must contain only numbers.")
#             return curve1_segs_arr, curve2_segs_arr
            
#     # Convert N x 8 array to list of (P0, P1, P2, P3) tuples for processing
#     def array_to_segment_list(segments_arr):
#         segment_list = []
#         for row in segments_arr:
#             P0 = row[0:2]
#             P1 = row[2:4]
#             P2 = row[4:6]
#             P3 = row[6:8]
#             segment_list.append((P0, P1, P2, P3))
#         return segment_list

#     # Convert list of (P0, P1, P2, P3) tuples back to N x 8 array
#     def segment_list_to_array(segment_list):
#         if not segment_list: return np.empty((0, 8), dtype=float)
#         segment_rows = [np.concatenate(seg) for seg in segment_list]
#         return np.array(segment_rows, dtype=float)

#     # --- Helper: Subdivide a list of segments --- 
#     def subdivide_to_bounds(segments_list, x_bounds):
#         if not segments_list: return [] 
#         x_bounds = sorted(list(set(x_bounds))) 
        
#         start_x = segments_list[0][0][0]
#         if x_bounds[0] < start_x - 1e-5:
#             x_bounds = [x for x in x_bounds if x >= start_x - 1e-5]
#             if not x_bounds: return segments_list
#             if abs(x_bounds[0] - start_x) < 1e-5: x_bounds[0] = start_x
#         elif abs(x_bounds[0] - start_x) > 1e-5:
#              x_bounds.insert(0, start_x)
#         else:
#              x_bounds[0] = start_x
             
#         new_segments_list = []
#         current_segments_queue = list(segments_list)
#         bound_index = 0

#         while current_segments_queue:
#             current_seg_tuple = current_segments_queue.pop(0)
#             # Ensure points are numpy arrays for calculation
#             P0, P1, P2, P3 = map(np.asarray, current_seg_tuple)
#             P0_x = P0[0]
#             P3_x = P3[0]
            
#             while bound_index < len(x_bounds) and x_bounds[bound_index] <= P0_x + 1e-5:
#                 bound_index += 1
            
#             if bound_index >= len(x_bounds) or x_bounds[bound_index] >= P3_x - 1e-5:
#                 new_segments_list.append(current_seg_tuple)
#                 continue
                
#             target_x = x_bounds[bound_index]
#             print(f"Subdividing segment [{P0_x:.2f} -> {P3_x:.2f}] at bound {target_x:.2f}")
#             try:
#                 # Pass the tuple representation to subdivide_segment
#                 seg1_tuple, seg2_tuple = subdivide_segment(current_seg_tuple, target_x)
#                 new_segments_list.append(seg1_tuple)
#                 current_segments_queue.insert(0, seg2_tuple) 
#             except Exception as e:
#                 print(f"Error subdividing segment at {target_x}: {e}. Adding original segment.")
#                 new_segments_list.append(current_seg_tuple) 
                 
#         return new_segments_list

#     # --- Main Logic --- 
#     # Convert input arrays to lists of tuples for processing
#     curve1_list = array_to_segment_list(curve1_segs_arr)
#     curve2_list = array_to_segment_list(curve2_segs_arr)
    
#     # Perform subdivision on the lists
#     new_curve1_list = subdivide_to_bounds(curve1_list, x_bounds)
#     new_curve2_list = subdivide_to_bounds(curve2_list, x_bounds)
    
#     # Convert results back to N x 8 arrays
#     new_curve1_arr = segment_list_to_array(new_curve1_list)
#     new_curve2_arr = segment_list_to_array(new_curve2_list)
    
#     return new_curve1_arr, new_curve2_arr


# def mix_bezsegs(curve1_segs_arr: np.ndarray, curve2_segs_arr: np.ndarray, mix_factor):
#     """
#     Mix two curves (N x 8 NumPy arrays) that have matching segmentation.
#     Linearly interpolates control points for corresponding segments.
#     Assumes segment arrays are of the same length (N).
    
#     Args:
#         curve1_segs_arr (np.ndarray): First curve as Nx8 array.
#         curve2_segs_arr (np.ndarray): Second curve as Nx8 array.
#         mix_factor (float): Interpolation factor (0.0 = curve1, 1.0 = curve2).
        
#     Returns:
#         np.ndarray: The mixed curve as a new Nx8 array.
#     """
#     # --- Input Validation ---
#     if not isinstance(curve1_segs_arr, np.ndarray) or curve1_segs_arr.ndim != 2 or curve1_segs_arr.shape[1] != 8:
#         print(f"Error: curve1_segs_arr must be an Nx8 NumPy array, got shape {curve1_segs_arr.shape if hasattr(curve1_segs_arr, 'shape') else type(curve1_segs_arr)}")
#         return np.empty((0, 8), dtype=float) # Return empty on error
#     if not isinstance(curve2_segs_arr, np.ndarray) or curve2_segs_arr.ndim != 2 or curve2_segs_arr.shape[1] != 8:
#         print(f"Error: curve2_segs_arr must be an Nx8 NumPy array, got shape {curve2_segs_arr.shape if hasattr(curve2_segs_arr, 'shape') else type(curve2_segs_arr)}")
#         return np.empty((0, 8), dtype=float)
        
#     if curve1_segs_arr.shape[0] != curve2_segs_arr.shape[0]:
#         print(f"Error: Curves must have the same number of segments to mix ({curve1_segs_arr.shape[0]} vs {curve2_segs_arr.shape[0]}). Returning first curve.")
#         # Consider if returning curve1 or empty is more appropriate
#         return curve1_segs_arr.copy() 

#     mix_factor = np.clip(mix_factor, 0.0, 1.0) # Ensure mix factor is valid [0, 1]

#     # --- Direct Array Interpolation --- 
#     # Leverage NumPy's vectorized operations for efficiency
#     mixed_segments_arr = (1.0 - mix_factor) * curve1_segs_arr + mix_factor * curve2_segs_arr
                 
#     return mixed_segments_arr
