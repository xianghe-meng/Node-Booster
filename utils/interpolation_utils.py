# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

import numpy as np

def curvemapping_to_bezsegs(curve) -> np.ndarray:
    """Convert a blender curvemapping directly to an N x 8 NumPy array of Bézier segments.
    Each row represents one segment: [P0x, P0y, P1x, P1y, P2x, P2y, P3x, P3y]
    Returns: segments_array: N x 8 NumPy array, or empty array if curve has < 2 points.
    """
    points = curve.points
    if len(points) < 2:
        # Return an empty array with the correct number of columns
        return np.empty((0, 8), dtype=float)
    
    segment_rows = [] # Temporary list to hold the 1x8 rows
    
    for i in range(len(points)-1):
        current = points[i]
        next_point = points[i+1]
        
        # Get anchor points (absolute coordinates from curve mapping)
        P0 = np.array([current.location.x, current.location.y], dtype=float)
        P3 = np.array([next_point.location.x, next_point.location.y], dtype=float)

        # Calculate Handle Positions (P1 and P2)
        # Vector handles: P1 coincides with P0, P2 coincides with P3
        # Auto handles: Approximate handle positions based on neighbors
        
        # Calculate P1 (Right Handle of current point)
        if (current.handle_type=='VECTOR'):
            P1 = P0.copy() 
        else:
             # Look behind if possible for smoother tangent
             if (i > 0):
                 prev_point = points[i-1]
                 P_prev = np.array([prev_point.location.x, prev_point.location.y], dtype=float)
                 tangent_prev = P0 - P_prev
                 tangent_next = P3 - P0
                 # Simple smooth approximation
                 P1 = P0 + (tangent_next - tangent_prev) / 6.0 + tangent_next / 3.0 
             # First point: only look ahead
             else: 
                 P1 = P0 + (P3 - P0) / 3.0

        # Calculate P2 (Left Handle of next point)
        if (next_point.handle_type=='VECTOR'):
            P2 = P3.copy()
        else:
            # Look ahead if possible for smoother tangent
            if (i < len(points) - 2):
                next_next_point = points[i+2]
                P_next_next = np.array([next_next_point.location.x, next_next_point.location.y], dtype=float)
                tangent_next = P3 - P0
                tangent_next_next = P_next_next - P3
                # Simple smooth approximation
                P2 = P3 - (tangent_next_next - tangent_next) / 6.0 - tangent_next / 3.0 
            # Last segment: only look behind
            else:
                P2 = P3 - (P3 - P0) / 3.0

        # Optional: Clamp handles to prevent extreme overshoot (basic version)
        dist_p0p3 = np.linalg.norm(P3-P0)
        if (dist_p0p3 > 1e-6): 
            if (np.linalg.norm(P1-P0) / dist_p0p3 > 1.0): 
                P1 = P0 + (P3-P0)/3.0
            if (np.linalg.norm(P2-P3) / dist_p0p3 > 1.0): 
                P2 = P3 - (P3-P0)/3.0

        # Flatten the 4 points into a single 1x8 row and add to list
        segment_row = np.concatenate((P0, P1, P2, P3))
        segment_rows.append(segment_row)

        continue

    # Convert the list of rows into a single Nx8 NumPy array
    segments_array = np.array(segment_rows, dtype=float)

    # Debug
    # print(f"Segments out: {segments_array}") 
    # print(f"Segments out type: {type(segments_array)}") 
    return segments_array

def reset_curvemapping(curve) -> None:
    """clear all points of this curve (2 pts need to be left)"""

    points = curve.points

    while (len(curve.points)>2):
        points.remove(points[1])

    points[0].location = (0,0)
    points[1].location = (1,1)

    return None

def bezsegs_to_curvemapping(curve, segments:np.ndarray) -> None:
    """Apply an N x 8 NumPy array of Bézier segments to a blender curvemapping.
    Assumes `segments` is a NumPy array where each row is: [P0x, P0y, P1x, P1y, P2x, P2y, P3x, P3y]
    """

    if (not isinstance(segments, np.ndarray)):
        raise ValueError("Input segments must be a NumPy array")
    if (segments.ndim != 2 or segments.shape[1] != 8):
        raise ValueError(f"Input segments array must have shape (N, 8), got {segments.shape}")

    num_segments = segments.shape[0]
    if (num_segments == 0):
        raise ValueError("Input segments array is empty")

    num_points = num_segments + 1
    reset_curvemapping(curve) # Start fresh with default 2 points

    # Ensure enough points exist in the Blender curve
    while len(curve.points) < num_points:
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
            
            # Determine and Set Handle Types
            # Direct comparison using NumPy arrays
            is_vector_start = np.allclose(P0, P1) 
            is_vector_end = np.allclose(P2, P3)
            
            # Set handle types in Blender CurveMappingPoint
            curve.points[i].handle_type = "VECTOR" if is_vector_start else "AUTO"
            curve.points[i+1].handle_type = "VECTOR" if is_vector_end else "AUTO"

        except Exception as e:
            print(f"WARNING: Unexpected error processing segment {i}: {e}")
            print(f"Segment data (row): {segments[i]}")
            continue 

    return None

# def evaluate_cubic_bezseg(segment, t):
#     """
#     Evaluate a cubic Bézier segment at parameter t (0 <= t <= 1).
#     evaluate tuple (P0, P1, P2, P3) with each point as a NumPy array.
#     Returns the point (as a NumPy array) on the curve.
#     """
#     # Ensure points are numpy arrays
#     try:
#         P0, P1, P2, P3 = map(np.asarray, segment)
#     except Exception as e:
#         print(f"Error converting segment points to numpy array in evaluate: {e}")
#         print(f"Segment data: {segment}")
#         return np.array([0.0, 0.0]) # Fallback
        
#     return (1-t)**3 * P0 + 3*(1-t)**2 * t * P1 + 3*(1-t)*t**2 * P2 + t**3 * P3

# def casteljau_subdiv_bezseg(segment, t):
#     """
#     Subdivide a cubic Bézier segment at parameter t using De Casteljau's algorithm.
#     Returns two new segments: (seg1, seg2)
#     """
#     try:
#         P0, P1, P2, P3 = [np.array(pt, dtype=float) for pt in segment]
#     except Exception as e:
#         print(f"Error converting segment points to numpy array in subdivide: {e}")
#         print(f"Segment data: {segment}")
#         # Return original segment split into two identical points? Or raise error?
#         fallback_pt = np.array([0.0, 0.0]) 
#         return (fallback_pt, fallback_pt, fallback_pt, fallback_pt), (fallback_pt, fallback_pt, fallback_pt, fallback_pt)
        
#     # De Casteljau calculation
#     Q0 = (1-t)*P0 + t*P1
#     Q1 = (1-t)*P1 + t*P2
#     Q2 = (1-t)*P2 + t*P3
#     R0 = (1-t)*Q0 + t*Q1
#     R1 = (1-t)*Q1 + t*Q2
#     S = (1-t)*R0 + t*R1
#     seg1 = (P0, Q0, R0, S)
#     seg2 = (S, R1, Q2, P3)
#     return seg1, seg2

# def subdivide_segment(segment, x_target, tol=1e-5, max_iter=50):
#     """
#     Subdivide a segment at the x-coordinate x_target.
#     Assumes the segment is monotonic in x for reliable binary search.
#     Uses a binary search to find t such that the x component of evaluate(segment, t) is x_target.
#     Returns two segments.
#     """
#     # Basic validation
#     if not segment or len(segment) != 4:
#         print(f"Invalid segment received in subdivide_segment: {segment}")
#         fallback_pt = np.array([0.0, 0.0]) 
#         return (fallback_pt, fallback_pt, fallback_pt, fallback_pt), (fallback_pt, fallback_pt, fallback_pt, fallback_pt)
        
#     P0_x = segment[0][0]
#     P3_x = segment[3][0]
    
#     # Handle edge cases where x_target is outside or at the segment boundaries
#     if x_target <= P0_x + tol: return casteljau_subdiv_bezseg(segment, 0.0)
#     if x_target >= P3_x - tol: return casteljau_subdiv_bezseg(segment, 1.0)
#     # Check for non-monotonicity (basic check, might not catch all cases)
#     if (P0_x > P3_x): 
#         print(f"Warning: Segment might be non-monotonic in X ({P0_x} -> {P3_x}). Subdivision might be unreliable.")
#         # Allow proceeding, but be aware results might be wrong if curve reverses in X

#     t_low, t_high = 0.0, 1.0
#     t_mid = 0.5 # Initialize t_mid
    
#     for _ in range(max_iter):
#         t_mid = (t_low + t_high) / 2
#         try:
#             pt = evaluate_cubic_bezseg(segment, t_mid)
#             x_val = pt[0] 
#         except Exception as e:
#             print(f"Error evaluating bezier segment during subdivision at t={t_mid}: {e}")
#             # Cannot proceed reliably, maybe return original segment split at t=0.5?
#             return casteljau_subdiv_bezseg(segment, 0.5)
            
#         if abs(x_val - x_target) < tol:
#             break # Found target t
            
#         # Adjust search range based on monotonicity assumption
#         if P0_x < P3_x: # Increasing X
#             if x_val < x_target:
#                 t_low = t_mid
#             else:
#                 t_high = t_mid
#         else: # Decreasing X (or potentially non-monotonic)
#             if x_val > x_target:
#                  t_low = t_mid
#             else:
#                  t_high = t_mid
                 
#     # Use the final t_mid for subdivision
#     return casteljau_subdiv_bezseg(segment, t_mid)

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
