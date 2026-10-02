import json
import csv
import sys
import os

def analyze(results_path):
    with open(results_path, "r") as f:
        results = json.load(f)
        
    summary = {}
    
    for r in results:
        frac = r["cf_fraction"]
        if frac not in summary:
            summary[frac] = {
                "total_trials": 0,
                "original_deadlocks": 0,
                "final_consensus": 0,
                "total_original_iterations": 0,
                "cf_recoveries": 0
            }
            
        stats = summary[frac]
        stats["total_trials"] += 1
        
        orig_deadlocked = r["original_summary"]["deadlocked"]
        if orig_deadlocked:
            stats["original_deadlocks"] += 1
            
        stats["total_original_iterations"] += r["original_summary"]["iterations"]
        
        if orig_deadlocked and r.get("counterfactual_summary"):
            if not r["counterfactual_summary"]["deadlocked"]:
                stats["cf_recoveries"] += 1
                stats["final_consensus"] += 1
        elif not orig_deadlocked:
            stats["final_consensus"] += 1
            
    csv_path = results_path.replace(".json", "_summary.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "cf_fraction", "total_trials", "deadlock_rate", 
            "consensus_rate", "mean_iterations", "cf_recovery_rate"
        ])
        
        for frac in sorted(summary.keys()):
            stats = summary[frac]
            t = stats["total_trials"]
            deadlock_rate = stats["original_deadlocks"] / t
            consensus_rate = stats["final_consensus"] / t
            mean_iter = stats["total_original_iterations"] / t
            
            if stats["original_deadlocks"] > 0:
                cf_recovery_rate = stats["cf_recoveries"] / stats["original_deadlocks"]
            else:
                cf_recovery_rate = 0.0
                
            writer.writerow([
                frac, t, deadlock_rate, consensus_rate, mean_iter, cf_recovery_rate
            ])
            
            print(f"Fraction: {frac}")
            print(f"  Trials: {t}")
            print(f"  Deadlock Rate: {deadlock_rate:.2f}")
            print(f"  Consensus Rate: {consensus_rate:.2f}")
            print(f"  Mean Iterations: {mean_iter:.2f}")
            print(f"  CF Recovery Rate: {cf_recovery_rate:.2f}")
            print("-" * 20)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze(sys.argv[1])
    else:
        # find most recent
        import glob
        files = glob.glob("experiments/results/results_*.json")
        if files:
            analyze(max(files, key=os.path.getctime))
        else:
            print("No results found.")
