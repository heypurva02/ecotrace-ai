# 🌿 EcoTrace AI

### AI-Assisted Product Sustainability Assessment Tool

EcoTrace AI is a web-based application that estimates the carbon footprint of products using activity data and emission factors across different life-cycle stages.

🔗 **Live Demo:** [Open EcoTrace AI](https://ecotrace-ai-eizpe6rhosmegtks5y3chq.streamlit.app/)

## ✨ Features

- 📊 **Dashboard:** View assessment statistics and carbon footprint visualizations.
- 📝 **New Assessment:** Enter product details and activity data.
- 📚 **Assessment History:** Access previously saved assessments.
- 🌍 **Environmental Analysis:** Explore emissions by life-cycle stage and category.
- ♻️ **Scenario Optimiser:** Compare alternative scenarios and estimate potential emission reductions.
- 🤖 **AI Sustainability Advisor:** Get rule-based sustainability recommendations.
- 📄 **Reports & Exports:** Export reports in PDF, CSV, and Excel formats.
- 🔬 **Methodology:** Review calculation methods, data sources, assumptions, and limitations.

## ⚙️ How It Works

1. Enter product information and activity quantities.
2. Apply the configured emission factors.
3. Calculate estimated emissions in kg CO₂e.
4. Visualize the environmental impact.
5. Compare scenarios and review recommendations.
6. Export assessment results.

**Basic formula:**

Estimated Emissions = Activity Data × Emission Factor

## 🛠️ Technology Stack

- Python
- Streamlit
- Pandas
- Plotly

*The technology stack should be verified against the project's actual dependencies.*

## 🚀 Run Locally

### Prerequisites

- Python
- pip
- Git

### Installation

Clone the repository:

```bash
git clone https://github.com/heypurva02/ecotrace-ai.git
cd ecotrace-ai
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
streamlit run app.py
```

Make sure `app.py` is the correct application entry point in your repository.

## 🧪 Testing

The project previously passed 49 automated tests after a fix to PDF report generation. Rerun the tests to verify the current version.

## ⚠️ Limitations

- Demonstration data and emission factors are illustrative and have not been independently verified.
- Results depend on input data, emission factors, and assumptions.
- The sustainability advisor currently uses rule-based recommendations.
- The application has not been independently validated or certified as a professional Life Cycle Assessment (LCA) platform.

**EcoTrace AI is an academic prototype** for learning, demonstration, and exploratory sustainability analysis.

## 🔮 Future Improvements

- Integration of verified emission-factor databases.
- Improved life-cycle assessment methods.
- Uncertainty and sensitivity analysis.
- More advanced sustainability recommendations.

## 📄 License

No open-source license has been specified yet.

---

**Built with 🌱 for a more sustainable future.**
