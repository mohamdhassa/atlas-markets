# PR29 security boundary

Frontend role checks hide ADMIN controls from USER sessions, while the existing backend ADMIN dependency remains the authorization boundary for automation mutations. No frontend action can enable Live Money through this Operations panel. Infrastructure mutation is outside scope.
