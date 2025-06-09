import json
import random
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

with open('problems.json') as f:
    PROBLEMS = json.load(f)

# index page template
INDEX_HTML = """
<!doctype html>
<title>LeetCode Random Selector</title>
<h1>Select Difficulty</h1>
<form action="/random" method="get">
  <select name="difficulty">
    <option value="Easy">Easy</option>
    <option value="Medium">Medium</option>
    <option value="Hard">Hard</option>
  </select>
  <button type="submit">Get Problem</button>
</form>
{% if problem %}
<h2>{{ problem.title }} ({{ problem.difficulty }})</h2>
<p><a href="{{ problem.url }}" target="_blank">{{ problem.url }}</a></p>
{% endif %}
"""

@app.route('/')
def index():
    difficulty = request.args.get('difficulty')
    problem = None
    if difficulty:
        matches = [p for p in PROBLEMS if p['difficulty'].lower() == difficulty.lower()]
        if matches:
            problem = random.choice(matches)
    return render_template_string(INDEX_HTML, problem=problem)

@app.route('/random')
def random_problem():
    difficulty = request.args.get('difficulty', '')
    matches = [p for p in PROBLEMS if p['difficulty'].lower() == difficulty.lower()]
    if not matches:
        return jsonify({'error': 'No problems found for difficulty'}), 404
    problem = random.choice(matches)
    # For index page uses this route via GET to display results.
    if request.accept_mimetypes.accept_html:
        return render_template_string(INDEX_HTML, problem=problem)
    return jsonify(problem)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
