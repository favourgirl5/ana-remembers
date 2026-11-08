"""Benchmark: how similar does the embedding model think two symptom descriptions are?

Used to choose MATCH_THRESHOLD in semantic.py: pairs that mean the same must score above it,
pairs that are different must score below it. Costs one embedding request per phrase
(free Gemini embedding model), no chat requests.
"""
from semantic import cosine, embed

SAME = [  # should be treated as the same concern
    ("palpitations", "my heart has been beating very fast"),
    ("palpitations", "racing heart"),
    ("ankle swelling", "swollen feet"),
    ("ankle and leg swelling", "my socks leave marks on my ankles"),
    ("breathlessness", "short of breath when I climb the stairs"),
    ("night cough", "coughing when I lie down at night"),
    ("weight gain", "my clothes feel tighter, I gained a few kilos"),
    ("low mood", "I feel down and hopeless"),
]
DIFFERENT = [  # must stay separate concerns
    ("ankle swelling", "abdominal swelling"),
    ("palpitations", "chest pain"),
    ("breathlessness", "night cough"),
    ("headache", "dizziness"),
    ("weight gain", "ankle swelling"),
    ("low mood", "reluctance to take medication"),
]

cache = {}
def vec(text):
    if text not in cache:
        cache[text] = embed(text)
    return cache[text]

print(f"{'Pair':<75}{'Score':>7}")
results = {}
for label, pairs in (("SAME", SAME), ("DIFFERENT", DIFFERENT)):
    print(f"\n{label}")
    results[label] = []
    for a, b in pairs:
        score = cosine(vec(a), vec(b))
        results[label].append(score)
        print(f"  {a + '  <->  ' + b:<73}{score:>7.3f}")

lowest_same = min(results["SAME"])
highest_diff = max(results["DIFFERENT"])
print(f"\nLowest SAME score:       {lowest_same:.3f}")
print(f"Highest DIFFERENT score: {highest_diff:.3f}")
if lowest_same > highest_diff:
    print(f"Clean split: a threshold of {(lowest_same + highest_diff) / 2:.2f} separates all pairs.")
else:
    print("Overlap: no threshold separates all pairs. Check which pairs cross.")