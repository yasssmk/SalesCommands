from django.urls import path
from .views.transcript_analysis_views import TranscriptAnalysisView
# from .views.apr_analysis_view import APRAnalysisView
# from .views.signal_view import SignalView

urlpatterns = [
    path('analyze-transcript/', TranscriptAnalysisView.as_view(), name='analyze-transcript'),
    # path('analyze-apd/', APRAnalysisView.as_view(), name='analyze-apd'),
    # path('analyze-apd/update-apd/', APRAnalysisView.as_view(), name='update-apd'),

    # # Signal CRUD
    # path('signals/', SignalView.as_view(), name='signal-list'),
    # path('signals/<int:pk>/', SignalView.as_view(), name='signal-detail'),
    
    # # Signal Actions
    # path('signals/<int:pk>/approve/', SignalView.as_view(), name='signal-approve'),
    # path('signals/<int:pk>/reject/', SignalView.as_view(), name='signal-reject'),
    # path('signals/<int:pk>/apply/', SignalView.as_view(), name='signal-apply'),
    # path('signals/<int:pk>/confirm/', SignalView.as_view(), name='signal-confirm'),
    # path('signals/<int:pk>/merge/', SignalView.as_view(), name='signal-merge'),
    
    # # Bulk Actions
    # path('signals/bulk-action/', SignalView.as_view(), name='signal-bulk-action'),
    
    # # Specialized Views
    # path('signals/by-entity/', SignalView.as_view(), name='signals-by-entity'),
    # path('signals/summary/', SignalView.as_view(), name='signals-summary'),

    # # New data-specific endpoints
    # path('signals/qualification-data/', SignalView.as_view(), name='qualification-data'),
    # path('signals/tech-evaluation-data/', SignalView.as_view(), name='tech-evaluation-data'),

]
