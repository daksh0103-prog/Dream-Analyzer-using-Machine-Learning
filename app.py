from flask import Flask, render_template, request
from ai_model import analyze_dream
from database import save_dream

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    dream_text = request.form['dream']
    result_text, analysis = analyze_dream(dream_text)
    save_dream("user1", dream_text, analysis)
    return render_template('index.html', dream=dream_text, result=result_text)

if __name__ == '__main__':
    app.run(debug=True)
