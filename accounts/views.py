from django.shortcuts import render, redirect
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.views.decorators.http import require_POST

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token




@require_POST
def logout_view(request):
    django_logout(request)
    return redirect("home")



def login_page(request):
    return render(request, "dashboard/login.html")



def register_page(request):
    return render(request, "dashboard/register.html")


@api_view(["GET"])
@permission_classes([AllowAny])
def registration_options_api(request):
    return Response({
        "roles": ["USER", "SELLER"]
    })



@api_view(["POST"])
@permission_classes([AllowAny])
def register_api(request):
    requested_role = request.data.get("role", "")

    
    if requested_role == "SUB_ADMIN":
        if not request.user.is_authenticated or not request.user.is_staff:
            return Response(
                {
                    "error": (
                        "Only an authorized admin can "
                        "create sub-admin accounts."
                    )
                },
                status=status.HTTP_403_FORBIDDEN
            )

    serializer = RegistrationSerializer(
        data=request.data,
        context={"request": request}
    )

    if serializer.is_valid():
        user = serializer.save()

        profile = getattr(user, "profile", None)

        return Response(
            {
                "message": "Registration successful.",
                "user": {
                    "id": user.id,
                    "full_name": user.get_full_name() or user.username,
                    "email": user.email,
                    "role": profile.role if profile else None,
                }
            },
            status=status.HTTP_201_CREATED
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST
    )



@api_view(["POST"])
@permission_classes([AllowAny])
def login_api(request):
    email = request.data.get("email", "")
    password = request.data.get("password", "")

    if not isinstance(email, str) or not isinstance(password, str):
        return Response(
            {"error": "Email and password must be text values."},
            status=status.HTTP_400_BAD_REQUEST
        )

    email = email.strip().lower()

    if not email or not password:
        return Response(
            {"error": "Email and password are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    account = User.objects.filter(email__iexact=email).first()

    if account is None:
        return Response(
            {"error": "Invalid email or password."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    user = authenticate(
        request,
        username=account.username,
        password=password
    )

    if user is None:
        return Response(
            {"error": "Invalid email or password."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if user.is_superuser:
        role = "ADMIN"
    else:
        profile = getattr(user, "profile", None)

        if profile is None:
            return Response(
                {"error": "This account has no assigned role."},
                status=status.HTTP_403_FORBIDDEN
            )

        role = profile.role

    if user.is_superuser or role == "SUB_ADMIN":
        redirect_url = "/admin-dashboard/"
    elif role == "SELLER":
        redirect_url = "/seller/"
    elif role == "USER":
        redirect_url = "/"
    else:
        return Response(
            {"error": "This account has an invalid role."},
            status=status.HTTP_403_FORBIDDEN
        )

    django_login(request, user)

    token, _ = Token.objects.get_or_create(user=user)

    return Response(
        {
            "message": "Login successful.",
            "token": token.key,
            "redirect_url": redirect_url,
            "user": {
                "id": user.id,
                "full_name": user.get_full_name() or user.username,
                "email": user.email,
                "role": role,
            }
        },
        status=status.HTTP_200_OK
    )


# API logout
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_api(request):
    if request.auth and hasattr(request.auth, "delete"):
        request.auth.delete()

    django_logout(request)

    return Response(
        {"message": "Logout successful."},
        status=status.HTTP_200_OK
    )



from django.http import JsonResponse

def session_test(request):
    return JsonResponse({
        "authenticated": request.user.is_authenticated,
        "username": (
            request.user.username
            if request.user.is_authenticated
            else None
        ),
        "session_key": request.session.session_key,
    })