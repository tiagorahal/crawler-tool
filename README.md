# HTML List Analyzer 🕵️‍♂️

A tool for complete analysis of HTML lists, designed to assist in the development of webcrawlers and scrapers.

---

## 📸 Screenshot

<img width="673" height="295" alt="image" src="https://github.com/user-attachments/assets/5f873187-e484-4dea-a23e-f5bfe564cb9b" />

---

## 📋 Features

- **Real HTML Sample**  
  Displays the actual HTML of the list and the first item, with a size limit to keep the interface clean.
  
- **Full Content List**  
  Shows all detected elements, numbered, with visual indicators for:
  - 🔗 Links
  - 🖼️ Images

- **Element Search (Global Finder) — NEW**  
  Search across everything the tool found on the page:
  - Scopes: Navigation menus, content lists, galleries, other lists, forms/inputs, links, headings, tables, content blocks
  - Query modes:
    - **Keyword** (case-insensitive; matches text content and common attributes like `id`, `class`, `href`, `src`, `name`, `type`)
    - **Advanced** (optional): **CSS** or **XPath** query for precise targeting
  - Results:
    - Grouped counters by type (e.g., items, links, forms, headings…)
    - Paginated result list with icons (🔗, 🖼️), text preview, and ready-to-copy selectors (CSS/XPath)
    - Highlighted matches and quick actions (copy selector, open link when applicable)

- **Type Classification**
  - 🧭 **Navigation Menus**
  - 📚 **Content Lists**
  - 🖼️ **Galleries**
  - 📝 **Other Lists**

- **Enhanced Visualization**
  - Two-column layout: technical info on the left, items on the right
  - Detailed statistics (total items, links, images, average text length)
  - Warning for very large lists

---

## 🚀 Benefits
- **Full** view of all items (not just a preview)
- Clear visual indicators for links and images
- Ready-to-copy HTML selectors (CSS and XPath)
- Makes creating and adjusting crawler selectors easier
- **Find anything fast** with a global search over all detected structures

---

## 🛠️ How to Use
1. Pass the page's HTML to the tool.
2. It will detect lists, classify them by type, and display:
   - Full list of items
   - Actual HTML of the list and the first item
   - Statistics and ready-to-use selectors
3. **Use the Element Search (Global Finder)**:
   - Enter a **keyword** to filter matches across all detected elements (lists, items, links, images, forms, headings, tables).
   - (Optional) Switch to **Advanced** and run a **CSS** or **XPath** query for precise selection.
   - Review the **grouped counts** and the **results table**, copy selectors, and open links where available.
4. Use this information to create or improve your webcrawler.

### 🔍 Search Examples
- Keyword: `login`, `CNPJ`, `article`, `button`
- CSS: `ul.content-list li a`, `.menu a[href]`, `table#results tr td:nth-child(1)`
- XPath: `//ul[contains(@class,'content-list')]//li//a`, `//form//input[@type='email']`, `//table//tr[td]`

---

## 📄 License
This project is licensed under the [MIT License](LICENSE) — free to use, but please keep credits.
