# Inventory Management System

A full-stack inventory management application built to track, update, and manage stock efficiently. Designed to simulate real-world inventory workflows with a focus on backend architecture and deployable systems.

---

## 🚀 Features

- Add, update, and delete inventory items (CRUD operations)
- Track stock levels across 100+ SKUs
- Input validation and structured workflows
- RESTful API-based backend
- Deployed for real-time usage

---

## 🛠 Tech Stack

- Backend: Flask (Python)
- Database: SQLite
- Frontend: HTML, CSS
- Deployment: Render

---

## 🌐 Live Demo

👉 https://inventory-mangement-s9ze.onrender.com/

---

## 📌 System Design

- Modular backend structure (routes, models, utils)
- REST API architecture for inventory operations
- Relational database schema (3–6 tables)
- Separation of concerns for scalability and maintainability

---

## 📷 Screenshots

![Dashboard](<Screenshot 2026-04-16 215948.png>) 
![Add item](image-1.png)

---

## ⚠️ Note on Data Persistence

This application currently uses SQLite for simplicity. When deployed on platforms like Render (free tier), the file system may reset, which can result in temporary data loss.  
In a production environment, this would be replaced with a persistent database such as PostgreSQL.

---

## ⚙️ Local Setup

```bash
git clone https://github.com/shakti-siva/inventory-management-system.git
cd inventory-management-system
pip install -r requirements.txt
python app.py