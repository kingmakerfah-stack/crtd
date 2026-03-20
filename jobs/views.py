from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.exceptions import NotFound
from .models import Job
from .serializers import JobSerializer
from .pagination import JobPagination
from drf_yasg.utils import swagger_auto_schema

class JobListCreateView(APIView):
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminUser()]
    
    @swagger_auto_schema(
            responses={
            200: JobSerializer(many=True),
        },
        operation_description="""
        Retrieve a paginated list of available jobs.
        This endpoint returns all job postings ordered by latest created first.
        Pagination is applied using the configured JobPagination class.

        Frontend can use this endpoint to display job listings in the job portal.
        """
    )

    # Returns list of jobs with pagination
    def get(self, request):
        jobs = Job.objects.all().order_by("-id")

        paginator = JobPagination()
        paginated_jobs = paginator.paginate_queryset(jobs, request)

        serializer = JobSerializer(paginated_jobs, many=True)
        return paginator.get_paginated_response(serializer.data)
    

    @swagger_auto_schema(
            request_body=JobSerializer,
            responses={
                201: JobSerializer,
                400: "Validation Error"
            },
            operation_description="""
            Create a new job posting.

            This endpoint allows administrators to create
            a new job listing by submitting the required job details.

            Required fields should be provided in the request body.
            """
    )
    # Create a new job
    def post(self, request):
        serializer = JobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class JobDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get_object(self, pk):
        try:
            return Job.objects.get(pk=pk)
        except Job.DoesNotExist:
            raise NotFound("Job not found")

    # Retrieve  
    '''
    def get(self, request, pk):
        job = self.get_object(pk)
        serializer = JobSerializer(job)
        return Response(serializer.data)
    '''
    @swagger_auto_schema(
        request_body=JobSerializer,
        responses={
            200: JobSerializer,
            400: "Validation Error",
            404: "Job not found"
        },
    operation_description="""
        Fully update an existing job.

        This endpoint replaces the entire job record with
        the data provided in the request body.

        All fields should be included when performing a PUT request.
        Fields not provided may be overwritten depending on serializer configuration.
        """
    )
    # Full update 
    def put(self, request, pk):
        job = self.get_object(pk)
        serializer = JobSerializer(job, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data,status=status.HTTP_200_OK)


    @swagger_auto_schema(
        request_body=JobSerializer,
        responses={
            200: JobSerializer,
            400: "Validation Error",
            404: "Job not found"
        },
        operation_description="""
        Partially update a job.

        This endpoint allows updating only specific fields of a job
        without replacing the entire object.

        Frontend may send only the fields that need to be updated.
        """
    )
    # Partial update 
    def patch(self, request, pk):
        job = self.get_object(pk)
        serializer = JobSerializer(job, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data,status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
    responses={
        204: "Job deleted successfully",
        404: "Job not found"
    },
    operation_description="""
        Delete a job posting.

        This endpoint removes the specified job record from the system.
        Once deleted, the job cannot be recovered.
        """
    )
    # Delete 
    def delete(self, request, pk):
        job = self.get_object(pk)
        job.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)