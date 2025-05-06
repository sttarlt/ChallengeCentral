# Architecture Overview - Musabaqati (مسابقاتي) Platform

## 1. Overview

Musabaqati (مسابقاتي) is an Arabic-language competition management platform that enables users to participate in competitions, earn points ("crypto" or "كربتو"), redeem rewards, and interact with other users. The platform features a comprehensive user management system, competition and reward systems, a points economy, social features, and a secure API.

The application is built as a monolithic Flask application with a PostgreSQL database, designed to provide a seamless Arabic-first user experience with a focus on security, performance, and scalability.

## 2. System Architecture

### 2.1 High-Level Architecture

The system follows a traditional web application architecture with the following components:

- **Frontend**: Server-rendered HTML templates with Bootstrap and custom CSS/JavaScript
- **Backend**: Python Flask application
- **Database**: PostgreSQL database
- **Authentication**: Custom Flask-Login implementation
- **Authorization**: Role-based access control with admin and regular user roles
- **API**: RESTful API with token-based authentication

### 2.2 Architectural Patterns

The application employs several architectural patterns:

1. **MVC Pattern**: Separation of concerns with models (database), views (templates), and controllers (routes)
2. **Blueprint Pattern**: Modular organization of routes with Flask Blueprints
3. **Repository Pattern**: Database access through model classes
4. **Middleware Pattern**: Request processing through Flask middleware for security, logging, etc.

## 3. Key Components

### 3.1 User Management System

- **Authentication**: Custom implementation using Flask-Login
- **User Roles**: Regular users and administrators with different permissions
- **Profile Management**: User profile data and settings
- **Session Management**: Secure session handling with proper timeout policies

### 3.2 Competition System

- **Competition Creation**: Admin-only competition creation and management
- **Participation Tracking**: User participation in competitions
- **Points Awarding**: Automatic and manual points distribution for competition winners

### 3.3 Rewards System

- **Reward Catalog**: Admin-managed catalog of available rewards
- **Redemption Process**: Points-to-rewards redemption with approval workflow
- **Inventory Management**: Tracking of reward availability and quantities

### 3.4 Points Economy

- **Points Packages**: Purchasable packages of points with different tiers
- **Points Transactions**: Comprehensive transaction logging and history
- **Points Transfer**: System for transferring points between users (referrals)

### 3.5 Social Features

- **Chat System**: Group and direct messaging capabilities
- **Referral System**: "Friend Challenge" (تحدي الصديق) for user acquisition with reward incentives
- **Leaderboards**: Competitive rankings based on points accumulation

### 3.6 Admin Dashboard

- **Competition Management**: Create, edit, and manage competitions
- **Reward Management**: Configure available rewards and handle redemption requests
- **User Management**: View and modify user data and point balances
- **System Configuration**: Platform-wide settings

### 3.7 API System

- **RESTful Endpoints**: Structured API endpoints for third-party integration
- **Authentication**: API key-based authentication with role-based permissions
- **Rate Limiting**: Protection against excessive API usage
- **Security Measures**: Comprehensive validation and protection mechanisms

## 4. Data Model

### 4.1 Core Entities

- **User**: User accounts and profiles
- **Competition**: Competition definitions and parameters
- **Participation**: User participation in competitions
- **Reward**: Available rewards for redemption
- **RewardRedemption**: Records of reward redemption requests
- **PointsTransaction**: History of all points movements
- **PointsPackage**: Purchasable points packages
- **PurchaseRecord**: Records of point package purchases

### 4.2 Social Entities

- **ChatRoom**: Group chat channels
- **ChatRoomMember**: Users' membership in chat rooms
- **Message**: Messages in chat rooms
- **Referral**: Referral relationships between users

### 4.3 API and Security Entities

- **APIKey**: API access keys for external integrations
- **APIFailedAuth**: Failed API authentication attempts
- **APIUsageLog**: API usage tracking
- **AdminNotification**: System notifications for administrators

## 5. Data Flow

### 5.1 User Authentication Flow

1. User submits login credentials via login form
2. System validates credentials against stored hashed passwords
3. Upon success, a secure session is established
4. Audit logging records the successful login event
5. User is redirected to the appropriate page based on role and previous activity

### 5.2 Competition Participation Flow

1. User browses available competitions
2. User registers for a competition through the participation form
3. System records participation and tracks completion status
4. Upon competition completion, points are awarded to the user
5. Points transaction is recorded in the transaction history

### 5.3 Reward Redemption Flow

1. User browses available rewards
2. User selects a reward to redeem with accumulated points
3. System validates point balance and reward availability
4. Redemption request is created and submitted for admin approval
5. Admin reviews and processes the redemption request
6. Upon approval, points are deducted from the user's balance
7. Redemption status is updated and user is notified

### 5.4 Points Purchase Flow

1. User selects a points package to purchase
2. User is directed to contact an administrator for payment
3. Admin processes the payment manually
4. Admin records the purchase and adds points to the user's account
5. Transaction is recorded in the purchase history and points transactions

### 5.5 API Interaction Flow

1. Client authenticates with API key
2. System validates the API key and permissions
3. Rate limiting checks are performed
4. Request is processed and response is generated
5. API usage is logged for auditing and monitoring

## 6. Security Architecture

### 6.1 Authentication Security

- Password hashing with secure algorithms
- Protection against brute force attacks through rate limiting
- Session management with secure cookies and proper expiration
- Admin verification for sensitive operations

### 6.2 API Security

- API key authentication with role-based permissions
- Rate limiting to prevent abuse
- Input validation and sanitization
- Origin validation through CORS configuration
- Request logging and monitoring

### 6.3 Data Security

- HTTPS enforcement in production
- Security headers for protection against common web vulnerabilities
- Secure handling of sensitive data
- Audit logging of sensitive operations

### 6.4 Fraud Prevention

- IP-based detection of suspicious activity
- Referral abuse prevention mechanisms
- Transaction monitoring for unusual patterns
- Administrative notifications for security events

## 7. External Dependencies

### 7.1 Core Dependencies

- **Flask**: Web framework
- **SQLAlchemy**: ORM for database interactions
- **Flask-Login**: Authentication management
- **Flask-WTF**: Form handling and validation
- **Flask-Limiter**: Rate limiting
- **Flask-CORS**: Cross-Origin Resource Sharing management

### 7.2 Additional Libraries

- **Gunicorn**: WSGI HTTP server
- **Pytest**: Testing framework
- **SendGrid**: Email delivery (imported but not fully implemented)

## 8. Deployment Strategy

### 8.1 Current Deployment

The application is currently deployed on Replit, with configuration in `.replit` file:

- **Web Server**: Gunicorn
- **Database**: PostgreSQL
- **External Port**: 80 (mapped to internal port 5000)

### 8.2 Production Recommendations

For a more robust production deployment, the application could be deployed:

1. Using containerization (Docker) for consistent environments
2. On cloud platforms like AWS, GCP, or Azure
3. With a proper CI/CD pipeline for automated testing and deployment
4. Behind a reverse proxy like Nginx for improved performance and security
5. With database scaling strategies as outlined in DATABASE.md

### 8.3 Scaling Considerations

As outlined in DATABASE.md, the application includes plans for scaling:

- Database index optimization at 1,000 MAU
- Database configuration tuning
- Data partitioning at 10,000 MAU
- Potential migration to dedicated database services

## 9. Future Architectural Considerations

### 9.1 Modularization Opportunities

- Further separation of concerns with more Flask Blueprints
- Potential migration to a microservices architecture for specific components
- Dedicated services for chat functionality and notification handling

### 9.2 Performance Improvements

- Implementation of caching for frequently accessed data
- Asynchronous processing for non-critical operations
- Background job processing for scheduled tasks

### 9.3 Frontend Evolution

- Potential adoption of a more interactive frontend framework
- API-driven frontend with separate backend services
- Mobile application development using the existing API

## 10. Development Workflow

- Local development with SQLite database
- Testing with pytest
- Manual deployment to Replit
- Security testing as outlined in SECURITY.md