# (c) Meta Platforms, Inc. and affiliates. Copyright
from django.http import Http404
from django.shortcuts import render, redirect
from django.views import View
from django.contrib.gis.geos import Point
from django.shortcuts import get_object_or_404

import csv
from workspace.models import AccessPointLocation, WorkspaceMapSession
from workspace import models as workspace_models
from workspace.forms import UploadTowerCSVForm, WorkspaceForms
from workspace.models.model_constants import KM_2_MI, M_2_FT
from guest_user.mixins import AllowGuestUserMixin, RegularUserRequiredMixin
from guest_user.functions import is_guest_user


class BulkUploadTowersView(RegularUserRequiredMixin, View):
    def post(self, request):
        try:
            csv_file = request.FILES.get("file", None)
            decoded_file = csv_file.read().decode("utf-8").splitlines()
            for row in csv.DictReader(decoded_file, delimiter=","):
                _, created = AccessPointLocation.objects.update_or_create(
                    owner=request.user,
                    name=row["Name"],
                    geojson=Point(y=float(row["Latitude"]), x=float(row["Longitude"])),
                    height=float(row["Height(ft)"]) / M_2_FT,
                    max_radius=float(row["Radius(mi)"]) / KM_2_MI,
                    session_id=request.session.session_key,
                    map_session_id=request.POST.get("map_session", None),
                )
            return redirect(request.GET.get("next", "/pro"))
        except Exception as e:
            raise e


class EditNetworkView(AllowGuestUserMixin, View):
    def get(self, request, session_id=None, name=None):
        if not is_guest_user(request.user):
            workspace_account = True
            if session_id is None:
                if workspace_models.WorkspaceMapSession.objects.filter(
                    owner=request.user
                ).exists():
                    session = (
                        workspace_models.WorkspaceMapSession.objects.filter(
                            owner=request.user
                        )
                        .order_by("-last_updated")
                        .first()
                    )
                    return redirect(
                        "workspace:edit_network", session.uuid, session.name
                    )
                else:
                    session = workspace_models.WorkspaceMapSession(owner=request.user)
                    session.save()
                    return redirect(
                        "workspace:edit_network", session.uuid, session.name
                    )

            session = get_object_or_404(
                workspace_models.WorkspaceMapSession,
                owner=request.user,
                uuid=session_id,
            )
        else:
            workspace_account = False
            if session_id:
                try:
                    session = get_object_or_404(
                        workspace_models.WorkspaceMapSession,
                        owner=request.user,
                        uuid=session_id
                    )
                except Http404:
                    return redirect("workspace:edit_account_network")
            else:
                session, _ = WorkspaceMapSession.get_or_create_demo_view(request)

        context = {
            "session": session,
            "workspace_account": workspace_account,
            "geojson": session.get_session_geojson(),
            "sidebar": session.get_sidebar_info(),
            "workspace_forms": WorkspaceForms(request, session),
            "should_collapse_link_view": True,
            "units": session.units_old,
            "tower_upload_form": UploadTowerCSVForm,
            "title": "LiDAR LOS Check - ISP Toolbox",
            "tool": "los_check",
            "demo_network_view": False,
        }
        return render(request, "workspace/pages/network_edit.html", context)
