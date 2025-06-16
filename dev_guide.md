# Developer Guide

This guide provides the full user and admin workflows for the Bot Management SaaS Platform. Every point has been derived from the finalized requirements and aligned with the current codebase structure.

---

## USER WORKFLOW

1. **Landing Page**
   - Publicly accessible for all users
   - Shows:
     - Project intro and features
     - Biggest active discount (if any)
     - “Login with Google” button (if not logged in)
     - Profile avatar + “Go to Dashboard” (if logged in)

2. **Login via Google**
   - New user → created in `clients` table with plan = NULL
   - Returning user:
     - If plan = NULL → redirect to plan selection
     - If plan exists → redirect to dashboard

3. **Plan Selection**
   - Two options:
     - Pre-defined package plans (admin-managed)
     - Custom plan builder (user selects apps)
   - Each supports Monthly / 6-Month / Yearly billing
   - System applies available discounts
   - After payment, plan and app access is assigned

4. **Dashboard Access**
   - After login + plan selection, user sees dashboard:
     - Allowed apps
     - Plan details and validity
     - Profile dropdown (Dashboard, My Apps, Manage Plan, Logout)

5. **App Usage**
   - User can:
     - Open assigned apps
     - Submit app feedback (ratings/comments)
     - Submit special/custom requests (retirement-based, etc.)

6. **Plan Expiry**
   - On expiry:
     - 3-day grace period starts
     - System alerts via:
       - Email
       - In-app popup
   - During grace:
     - User can renew, upgrade, downgrade
   - After grace:
     - App access is blocked

7. **Custom Bundle Flow**
   - User selects apps (each app has a fixed price)
   - System applies bundle discounts (based on count/duration)
   - Completes payment
   - Apps assigned, user redirected to dashboard

---

## ADMIN WORKFLOW

1. **Admin Login**
   - Admin logs in using fixed ID/password from database (`admin` / `admin123`)
   - Accesses secure admin dashboard

2. **Dashboard Overview**
   - Summary view showing:
     - Total users, total apps
     - Active and expired plans
     - Revenue analytics
     - Alerts and flagged feedback

3. **Package Plan Management**
   - Create/Edit/Delete plans
   - Set pricing for:
     - Monthly
     - 6-Months
     - Yearly
   - Assign apps to each plan
   - Toggle plan active/inactive

4. **App (Bot) Upload and Management**
   - Upload app as `.zip` (must contain `app.py`)
   - System:
     - Extracts + validates Flask app
     - Renames entry file as `main.py`
     - Installs `requirements.txt` via `venv.bat`
     - Registers app via DispatcherMiddleware under `/bot-name`
   - Admin provides:
     - Name
     - Icon
     - Fixed price (used in custom bundles)
   - Admin can:
     - Edit or delete apps
     - Restart or stop apps
     - Update app zip and metadata

5. **Discount Management**
   - Create plan-specific and bundle-specific discounts
   - Set:
     - Name, value (%, ₹)
     - Duration (start–end date)
     - Active toggle
   - Expired discounts are hidden from user flow
   - Highest valid discount shown on landing

6. **Bundle Discount Rules**
   - Configure:
     - Per-app count thresholds (e.g., 3 apps = 10% off)
     - Separate tiers for Monthly, 6-Month, Yearly
   - Applied in custom bundle pricing

7. **App Pricing for Custom Plans**
   - Each app has a fixed price
   - Used in custom bundle builder
   - Editable any time from admin panel

8. **User Management**
   - View all users, filter by status/plan
   - View user profiles:
     - Plan, apps, payment history
   - Admin actions:
     - Extend plans
     - Revoke apps
     - Delete user

9. **Customer Requests**
   - View all requests with:
     - Type, description, status
   - Admin can approve/reject/respond
   - Responses are logged

10. **Feedback Moderation**
    - View and manage:
      - Ratings
      - Comments
      - Reported/flagged items
    - Admin can delete, resolve, or respond

11. **Payment Logs**
    - Full history:
      - Plan ID / App Bundle ID
      - Amount
      - Razorpay Ref ID
    - Export as CSV

12. **Audit Logs**
    - Every admin action is logged:
      - Upload, edit, delete
      - Plan changes
      - Discount changes
    - Admins can filter/search

13. **Settings**
    - Global controls:
      - SMTP Email settings
      - OAuth / Razorpay credentials
      - Grace period length
      - UI control switches

14. **Analytics & Reports**
    - Monthly revenue
    - Most used apps
    - Plan performance
    - Bundle vs. package usage ratio

---

This document will be updated as new modules are introduced.
