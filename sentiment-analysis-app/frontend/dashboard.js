let chart;

// Your logged-in user's ID (get this from login response)
const userId = localStorage.getItem("user_id");
const loadingOverlay = document.getElementById("loadingOverlay");


// Analyze subreddit using FastAPI backend
async function analyzeKeyword() {
    const keyword = document.getElementById("keyword").value.trim();
    if (!keyword) {
        alert("Please enter a subreddit name!");
        return;
    }

    // Show loading screen
    loadingOverlay.style.display = "flex";

    try {
        // Wait 4 seconds before fetching (smooth loading)
        await new Promise(resolve => setTimeout(resolve, 4000));

        const res = await fetch(`http://127.0.0.1:8000/analyze/${userId}/${keyword}`);
        const data = await res.json();

        // Hide loader
        loadingOverlay.style.display = "none";

        // Handle error or empty results
        if (!data.result || data.status === "error" || data.result.total_comments === 0) {
            alert("No comments found for this subreddit. Try another keyword!");
            return;
        }

        const result = data.result;

        // Update pie chart
        if (chart) chart.destroy();
        chart = new Chart(document.getElementById("sentimentChart"), {
            type: "pie",
            data: {
                labels: ["Positive", "Negative", "Neutral"],
                datasets: [{
                    data: [result.positive, result.negative, result.neutral],
                    backgroundColor: ["#4caf50", "#f44336", "#ff9800"]
                }]
            }
        });

        // Reload history after analysis
        loadHistory();

    } catch (error) {
        // Hide loader and show error alert
        loadingOverlay.style.display = "none";
        console.error("Error:", error);
        alert("Something went wrong while analyzing. Please try again!");
    }
}

// Load history from backend
async function loadHistory() {
    const list = document.getElementById("historyList");
    list.innerHTML = "";

    const res = await fetch(`http://127.0.0.1:8000/history/${userId}`);
    const data = await res.json();

    if (data.status === "error") {
        list.innerHTML = "<li>No history found yet.</li>";
        return;
    }

    data.history.forEach(item => {
        const li = document.createElement("li");
        li.innerHTML = `
            <b>${item.subreddit}</b> - ${item.timestamp}<br>
            Positive: ${item.positive}% | Negative: ${item.negative}% | Neutral: ${item.neutral}%<br>
            <a href="http://127.0.0.1:8000${item.pdf_url}" target="_blank">
                <button>Download Report</button>
            </a>
        `;
        list.appendChild(li);
    });
}

// Call history on load
window.onload = () => {
    if (userId) loadHistory();
    else alert("Please log in first.");
};
