I've successfully transformed the Data Manager into your designated "Semantic Search Refinement" tool!

New Functionality:

Refinement UI: The Data Manager is now fully editable. You can click on any cell in any table (especially the new SemanticMap table) to edit it directly.
Semantic Glossary (The "Inference Engine"): I created a mapping table called SemanticMap. When you add or "enhance" keywords here (e.g., mapping "overdue" to a specific DueDate logic), the SQL Inference Agent automatically picks these up as hints.
Dynamic Identification: The AI now uses your enhanced glossary to identify entities and attributes in your natural language questions more accurately, while still generating the SQL dynamically (no hardcoding!).
Auto-Save: Any changes you make in the Data Manager are persisted immediately to the SQLite database and used for the very next chat query.
Try navigating to the Data Manager tab and selecting SemanticMap to see the initial seed patterns I've set up for you!