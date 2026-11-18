# 🎉 Event Management System

## 📌 Project Overview

The **Event Management System** is a web-based application developed using Python and Django that simplifies the process of managing events, handling bookings, and organizing event-related services.

The platform provides users with an easy-to-use interface to explore available events, book event packages, manage their profiles, and handle payments. It also provides an administrative dashboard to manage events, packages, bookings, and users efficiently.

## 🚀 Features

- **User Authentication:** Secure user registration and login functionality.
- **User Dashboard:** Personalized dashboard for managing user activities.
- **Event Management:** Browse and manage available events.
- **Booking Management:** Create, view, and manage event bookings.
- **User Profile:** Manage and update personal information.
- **Custom Packages:** Explore and create customized event packages.
- **Payment Management:** Handle payment-related operations.
- **Admin Dashboard:** Manage users, events, packages, and bookings.
- **Responsive Design:** User-friendly interface across different screen sizes.

## 🛠️ Technologies Used

**Backend:**
- Python
- Django

**Frontend:**
- HTML5
- CSS3
- JavaScript
- Bootstrap 

**Database:**
- PostgreSQL
- SQLite

**Tools:**
- Git & GitHub
- Visual Studio Code / PyCharm

## ⚙️ Installation and Setup

Follow these steps to run the project locally.

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/EventManagement.git
```

### 2. Navigate to the Project Directory

```bash
cd EventManagement
```

### 3. Create a Virtual Environment

```bash
python -m venv .venv
```

### 4. Activate Virtual Environment

**Windows:**

```bash
.venv\Scripts\activate
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Apply Database Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Run the Development Server

```bash
python manage.py runserver
```

Open your browser and visit:

```text
http://127.0.0.1:8000/
```

## 📂 Project Structure

```text
EventManagement/
│
├── bookings/
├── config/
├── dashboard/
├── events/
├── packages/
├── payments/
├── templates/
├── static/
├── manage.py
├── requirements.txt
└── README.md
```

## 🎯 Project Objective

The main objective of this project is to develop a centralized platform that makes event planning and management easier,
more organized, and efficient for both customers and administrators.

## 🔮 Future Enhancements

- Online payment gateway integration.
- Email notifications for booking confirmations.
- Advanced event search and filtering.
- Booking history and tracking.
- Improved analytics and reporting dashboard.

## 👨‍💻 Author

**Sohail Khan**

GitHub: https://github.com/your-username

---

⭐ If you find this project useful, consider giving it a star!
