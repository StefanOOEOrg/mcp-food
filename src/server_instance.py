"""Shared MCPServer instance that tool modules register themselves against."""
from mcp.server.mcpserver import MCPServer

INSTRUCTIONS = """\
Food database: nutrition values of foods and of the user's recipes. This server only supplies
the numbers; it never records what was eaten. Meals are recorded with meal_log of the server
mcp-nutrition.

Sources of foods (parameter `source` of food_search):
- "my":  the user's own foods (products eaten often, values from labels). Checked first.
- "off": Open Food Facts, products sold in Austria (packaged, branded: "Spar Vital Skyr").
- "bls": BLS 4.0, the German food composition table, for basic ingredients
         ("Haferflocken", "Hähnchenbrust roh"). Austrian words are translated automatically.
Every food has a food_id. Values are per 100 g unless a field says otherwise.

To get the values of a meal:
1. Home-cooked dish? recipe_list shows the saved recipes.
   Otherwise food_search(query) per component, or food_barcode_lookup(barcode).
2. food_nutrition(items=[...]) with every component and its amount: one call, returns the
   values of each component and the total.
3. Pass the total to meal_log (mcp-nutrition); the field names are the same
   (kcal, protein_g, carbs_g, fat_g, fiber_g, sugar_g).
Only if nothing fits, estimate - and say that it is an estimate.

A product that is not in the database (or has wrong values) is saved with food_save from
the label; next time food_search finds it under source "my".
"""

server = MCPServer(name="mcp-food", instructions=INSTRUCTIONS)
