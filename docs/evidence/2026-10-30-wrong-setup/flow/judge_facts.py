#!/usr/bin/env python3
"""What a judge of reasons-to-judge.jsonl needs beyond each run's change: what the frames hold, from
flow/frame-facts.json and the design. The second question asks for the actual change or its visible effect, and the
change alone does not say what is visible in the window.

Usage: python3 judge_facts.py   (in this folder; standard library only; writes ../judge-facts.json)
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NORMAL = ("N1", "N2", "N3", "N4", "N5")


def main():
    facts = json.loads((HERE / "frame-facts.json").read_text())
    design = json.loads((HERE.parent / "test-set" / "design.json").read_text())
    by_run, frames = facts["by_run"], facts["frames"]
    changes = {run["name"]: run["change"] for run in design["runs"]}
    patches = facts["mesh"]["patches"]

    def merged(name, runs):
        return min(by_run[r][name][0] for r in runs), max(by_run[r][name][1] for r in runs)

    def share(pair):
        return f"{100 * pair[0]:.1f} %" if f"{pair[0]:.3f}" == f"{pair[1]:.3f}" else f"{100 * pair[0]:.1f} to {100 * pair[1]:.1f} %"

    def number(pair, digits=3):
        return f"{pair[0]:.{digits}g} to {pair[1]:.{digits}g}"

    normal_area = share(merged("reversed_share_of_window_by_area", NORMAL))
    normal_below = share(merged("reversed_share_below_step_height_by_area", NORMAL))
    normal_cells = share(merged("reversed_share_of_window_by_cells", NORMAL))
    normal_low_ux = number(merged("lowest_Ux_in_window", NORMAL))
    normal_wall = share(merged("wall_reversed_share_of_the_window_length", NORMAL))
    normal_p = number(merged("colour_bar_p_lower_end", NORMAL), 4)
    normal_thin = number(merged("thin_layer_mean_speed", NORMAL), 2)
    neighbours = facts["neighbouring_frames_of_a_run"]
    against = facts["pictures_against_n5_at_the_same_step"]
    others = ("N1", "N2", "N3", "N4")
    m5 = facts["m5"]
    split = m5["upper_minus_lower_half_mean_Ux_m_per_s_at_step_8000"]["M5"]
    layer = facts["m4_upper_wall_layer"]["by_step"]

    out = {
        "use": "Give this to a judge of reasons-to-judge.jsonl with the question. A reason is judged against what the frames "
               "hold: the change itself, or an effect that is visible in the window. Measured from the arrays, the mesh and the "
               "pictures (flow/frame_facts.py); no model answer was used.",
        "all_frames": [
            f"The window is x 0 to 0.12 m, y 0 to 0.04 m. The step's lip is at x = 0, y = {facts['step_lip_m']['y']} m, on the left "
            f"edge at 32 % of the height, and the window starts there. No picture has a white area: "
            f"{facts['white_pixels']['white_pixels_inside_axes']} white pixels inside the axes in "
            f"{facts['white_pixels']['pictures']} pictures. A reason that no step or no white area can be seen describes the plot "
            "window and holds for all 80 frames.",
            f"The inlet is at x = {patches['inlet']['x_m'][0]} m, the outlet at x = {patches['outlet']['x_m'][0]} m and the upper "
            f"wall at y = {patches['upperWall']['y_m'][0]} m, all outside the window.",
            f"In the normal frames reverse flow (Ux < 0) covers {normal_area} of the window's area ({normal_cells} of its cells), "
            f"and the lowest Ux is {normal_low_ux} m/s."],
        "runs": {
            "M1-inlet-speed": {
                "change": changes["M1-inlet-speed"],
                "what_the_frames_hold": [
                    f"The |U| colour bar ends at {number(by_run['M1-inlet-speed']['colour_bar_U_upper_end'], 4)} m/s, under the stated "
                    "32.2 m/s.",
                    f"The fastest flow in the window is reverse flow left from the start state (lowest Ux {number(by_run['M1-inlet-speed']['lowest_Ux_in_window'])} "
                    "m/s, minus the peak |U| at every frame), not flow at the inlet's 3.22 m/s, which has crossed about one window "
                    "length by the end of the run."]},
            "M2-viscosity": {
                "change": changes["M2-viscosity"],
                "what_the_frames_hold": [
                    f"Recirculation is not missing. Reverse flow covers {share(by_run['M2-viscosity']['reversed_share_of_window_by_area'])} "
                    f"of the window's area (normal frames {normal_area}) and {share(by_run['M2-viscosity']['reversed_share_below_step_height_by_area'])} "
                    f"of the part below the step's height (normal {normal_below}).",
                    f"Next to the lower wall it covers {share(by_run['M2-viscosity']['wall_reversed_share_of_the_window_length'])} of the "
                    f"window's length (normal {normal_wall}), unbroken from x = {by_run['M2-viscosity']['wall_reverse_flow_starts_x_m'][0] * 1000:.1f} mm "
                    f"to x = {number(by_run['M2-viscosity']['wall_first_stretch_ends_x_m'], 4)} m, so the bubble is longer than the window.",
                    f"It is weak: lowest Ux {number(by_run['M2-viscosity']['lowest_Ux_in_window'])} m/s (normal {normal_low_ux} m/s).",
                    "So a reason that there is no recirculation or no separation is false as a statement about the flow.",
                    f"What is visible is the absence of vortices and a smooth p: lowest p {number(by_run['M2-viscosity']['colour_bar_p_lower_end'], 4)} "
                    f"m^2/s^2 (normal {normal_p}); neighbouring frames of the run differ by a mean of "
                    f"{number(neighbours['M2-viscosity']['positions_mean_U_range'])} of the 256 colours in the |U| picture (normal "
                    f"{number((min(neighbours[r]['positions_mean_U_range'][0] for r in NORMAL), max(neighbours[r]['positions_mean_U_range'][1] for r in NORMAL)))})."]},
            "M3-slip-walls": {
                "change": changes["M3-slip-walls"],
                "what_the_frames_hold": [
                    f"The lower wall has no boundary layer: mean speed in the cells below y = 0.8 mm is {number(by_run['M3-slip-walls']['thin_layer_mean_speed'], 3)} m/s "
                    f"(normal {normal_thin} m/s), a bright layer along the bottom edge.",
                    f"The |U| colour bar starts at {number(by_run['M3-slip-walls']['colour_bar_U_lower_end'], 3)} m/s (normal at most "
                    f"{merged('colour_bar_U_lower_end', NORMAL)[1]:.3g} m/s).",
                    "The upper wall is outside the window."]},
            "M4-moving-wall": {
                "change": changes["M4-moving-wall"],
                "what_the_frames_hold": [
                    f"The change is not in the pictures. The reverse flow along the moved wall reaches down to the cell centred at y = "
                    f"{min(row['layer_lowest_cell_y_m_over_x_0p001_to_0p119'] for row in layer.values()):.4f} m at the lowest, and the "
                    f"picture ends at y = {facts['window_m']['y'][1]} m.",
                    f"The frames lie close to N5's at the same step: mean velocity difference over the window's cells "
                    f"{share(against['M4-moving-wall']['mean_velocity_difference_over_32p2_by_cells_range'])} of 32.2 m/s, against "
                    f"{share((min(against[r]['mean_velocity_difference_over_32p2_by_cells_range'][0] for r in others), max(against[r]['mean_velocity_difference_over_32p2_by_cells_range'][1] for r in others)))} "
                    "for N1 to N4.",
                    "So a reason on these frames cannot come from a sight of the change itself."]},
            "M5-half-inlet": {
                "change": changes["M5-half-inlet"],
                "what_the_frames_hold": [
                    "The split of the inlet is not in the pictures. At the last frame the upper half of the channel runs faster than the "
                    "lower half by " + ", ".join(f"{value:.1f} m/s at x = {place} m" for place, value in split.items() if float(place) in (-1.5, -1.2, -0.9, -0.6, -0.3))
                    + ".",
                    f"Just upstream of the step's lip (x = {m5['at_the_step']['x_m']} m, last frame) the core profile is flat at "
                    f"{number(m5['at_the_step']['M5_core_Ux_y_0p03_to_0p1_m'])} m/s, against {number(m5['at_the_step']['N5_core_Ux_y_0p03_to_0p1_m'])} m/s in N5: "
                    "half the flow rate, not a jet.",
                    f"The clearest visible effect is the lower speed: the |U| colour bar ends at {number(by_run['M5-half-inlet']['colour_bar_U_upper_end'], 4)} m/s."]}}}
    (HERE.parent / "judge-facts.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
