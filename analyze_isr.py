
import argparse
import re
from dataclasses import dataclass
from typing import List, Tuple
import pandas as pd

OVERHEAD_LABELS = {
    "switch to kernel mode": "mode_switch",
    "context saved": "context_saved",
    "find vector": "find_vector",
    "load address": "load_pc",
    "IRET": "iret",
    "context restored": "context_restored",
}

CPU_LABEL = "CPU burst"

@dataclass
class Line:
    start: int
    dur: int
    text: str

def classify_label(text: str) -> str:
    if text == CPU_LABEL:
        return "cpu"
    for k in OVERHEAD_LABELS.keys():
        if text.startswith(k):
            return "overhead"
    return "body"

def parse_execution(path: str) -> Tuple[List[Line], pd.DataFrame]:
    lines: List[Line] = []
    with open(path, "r") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            parts = raw.split(",", 2)
            if len(parts) != 3:
                parts = [p.strip() for p in re.split(r"\s*,\s*", raw, maxsplit=2)]
            if len(parts) != 3:
                continue
            start_s, dur_s, text = parts
            try:
                start = int(start_s.strip())
                dur = int(dur_s.strip())
            except:
                continue
            text = text.strip()
            lines.append(Line(start, dur, text))

    df = pd.DataFrame([{"start": l.start, "dur": l.dur, "text": l.text,
                        "kind": classify_label(l.text)} for l in lines])
    return lines, df

def summarize(df: pd.DataFrame):
    total_time = df["dur"].sum()
    cpu_time = df.loc[df["kind"]=="cpu", "dur"].sum()
    overhead_time = df.loc[df["kind"]=="overhead", "dur"].sum()
    body_time = df.loc[df["kind"]=="body", "dur"].sum()

    overhead_breakdown = (
        df[df["kind"]=="overhead"]
        .assign(label=df["text"].map(lambda s: next((OVERHEAD_LABELS[k] for k in OVERHEAD_LABELS if s.startswith(k)), "overhead")))
        .groupby("label")["dur"].sum()
        .rename_axis("overhead_component").reset_index()
    )

    summary = pd.DataFrame({
        "metric": ["total_time", "cpu_time", "overhead_time", "body_time"],
        "ms": [total_time, cpu_time, overhead_time, body_time]
    })
    return summary, overhead_breakdown

def what_if_save(df: pd.DataFrame, new_save: int):
    dff = df.copy()
    is_save = dff["text"].str.startswith("context saved")
    dff.loc[is_save, "dur"] = new_save
    total_time = dff["dur"].sum()
    cpu_time = dff.loc[dff["kind"]=="cpu", "dur"].sum()
    overhead_time = dff.loc[dff["kind"]=="overhead", "dur"].sum()
    body_time = dff.loc[dff["kind"]=="body", "dur"].sum()
    return int(total_time), int(cpu_time), int(overhead_time), int(body_time)

def what_if_scale_body(df: pd.DataFrame, scale=None, target=None):
    dff = df.copy()
    if scale is not None and target is not None:
        raise ValueError("Specify either scale or target, not both.")
    if scale is not None:
        dff.loc[dff["kind"]=="body", "dur"] = (dff.loc[dff["kind"]=="body", "dur"] * scale).round().astype(int).clip(lower=1)
    elif target is not None:
        # Proportionally rescale body lines within each interrupt so their sum equals 'target'
        inside = False
        cur_body_rows = []
        cur_body_sum = 0
        for i, row in dff.iterrows():
            text = row["text"]
            if text.startswith("switch to kernel mode"):
                inside = True
                cur_body_rows = []
                cur_body_sum = 0
            if inside and row["kind"] == "body":
                cur_body_rows.append(i)
                cur_body_sum += int(row["dur"])
            if text == "IRET" and inside:
                if cur_body_rows:
                    if cur_body_sum == 0:
                        k = len(cur_body_rows)
                        base = max(1, target // k)
                        rem = max(0, target - base*k)
                        for j, idx_row in enumerate(cur_body_rows):
                            nv = base + (1 if j < rem else 0)
                            dff.at[idx_row, "dur"] = nv
                    else:
                        factor = target / cur_body_sum
                        new_vals = [max(1, int(round(int(dff.at[idx_row, 'dur']) * factor))) for idx_row in cur_body_rows]
                        diff = target - sum(new_vals)
                        j = 0
                        while diff != 0 and new_vals:
                            take = 1 if diff > 0 else -1
                            if new_vals[j] + take >= 1:
                                new_vals[j] += take
                                diff -= take
                            j = (j + 1) % len(new_vals)
                        for idx_row, nv in zip(cur_body_rows, new_vals):
                            dff.at[idx_row, "dur"] = nv
                inside = False
                cur_body_rows = []
                cur_body_sum = 0

    total_time = int(dff["dur"].sum())
    cpu_time = int(dff.loc[dff["kind"]=="cpu", "dur"].sum())
    overhead_time = int(dff.loc[dff["kind"]=="overhead", "dur"].sum())
    body_time = int(dff.loc[dff["kind"]=="body", "dur"].sum())
    return total_time, cpu_time, overhead_time, body_time

def main():
    ap = argparse.ArgumentParser(description="Analyze ISR simulation logs and run what-if scenarios.")
    ap.add_argument("files", nargs="+", help="execution.txt file(s) to analyze")
    ap.add_argument("--save", type=int, nargs="*", default=None, help="Try these SAVE (context saved) durations and report totals")
    ap.add_argument("--scale-body", type=float, default=None, help="Multiply all ISR body line durations by this factor (what-if)")
    ap.add_argument("--target-body", type=int, default=None, help="Set EACH interrupt's body TOTAL to this ms (what-if)")
    ap.add_argument("--csv", type=str, default=None, help="Write a CSV summary here")
    args = ap.parse_args()

    rows = []
    for path in args.files:
        _, df = parse_execution(path)
        base_summary, base_over = summarize(df)

        print(f"=== {path} ===")
        print(base_summary.to_string(index=False))
        print("\nOverhead breakdown:")
        print(base_over.to_string(index=False))

        if args.save:
            for sv in args.save:
                T, CPU, OH, BODY = what_if_save(df, sv)
                rows.append({"file": path, "scenario": f"SAVE={sv}", "total": T, "cpu": CPU, "overhead": OH, "body": BODY})

        if args.scale_body is not None:
            T, CPU, OH, BODY = what_if_scale_body(df, scale=args.scale_body)
            rows.append({"file": path, "scenario": f"scale_body={args.scale_body}", "total": T, "cpu": CPU, "overhead": OH, "body": BODY})

        if args.target_body is not None:
            T, CPU, OH, BODY = what_if_scale_body(df, target=args.target_body)
            rows.append({"file": path, "scenario": f"target_body={args.target_body}", "total": T, "cpu": CPU, "overhead": OH, "body": BODY})

        base_total = int(df["dur"].sum())
        base_cpu = int(df.loc[df["kind"]=="cpu", "dur"].sum())
        base_overhead = int(df.loc[df["kind"]=="overhead", "dur"].sum())
        base_body = int(df.loc[df["kind"]=="body", "dur"].sum())
        rows.append({"file": path, "scenario": "baseline", "total": base_total, "cpu": base_cpu, "overhead": base_overhead, "body": base_body})

        print("")

    if rows:
        out = pd.DataFrame(rows)[["file", "scenario", "total", "cpu", "overhead", "body"]]
        print("=== Scenario summary ===")
        print(out.to_string(index=False))
        if args.csv:
            out.to_csv(args.csv, index=False)
            print(f"\nWrote CSV to {args.csv}")

if __name__ == "__main__":
    main()
