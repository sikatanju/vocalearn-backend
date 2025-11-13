from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

User = get_user_model()


class SavedItem(models.Model):
    """Unified model for all saved content types"""
    
    ITEM_TYPES = [
        ('translation', 'Translation'),
        ('speech_to_text', 'Speech to Text'),
        ('pronunciation', 'Pronunciation Assessment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_items')
    type = models.CharField(max_length=20, choices=ITEM_TYPES)
    
    # Core content stored as JSON
    content = models.JSONField(
        help_text="Flexible JSON structure based on item type"
    )
    
    # Common fields
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Language fields
    source_language = models.CharField(max_length=10, blank=True, help_text="ISO language code")
    target_language = models.CharField(max_length=10, blank=True, help_text="ISO language code")
    
    # Audio reference
    audio_url = models.TextField(blank=True, help_text="S3/storage reference for audio files")
    audio_size_bytes = models.BigIntegerField(default=0, help_text="Size of audio file in bytes")
    
    # SRS (Spaced Repetition System) fields
    ease_factor = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=2.5,
        validators=[MinValueValidator(1.3)]
    )
    interval_days = models.IntegerField(default=0)
    repetitions = models.IntegerField(default=0)
    next_review_date = models.DateField(null=True, blank=True, db_index=True)
    
    # Full-text search
    search_vector = SearchVectorField(null=True, editable=False)
    
    class Meta:
        db_table = 'saved_items'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'type'], name='idx_user_type'),
            models.Index(fields=['user', 'next_review_date'], name='idx_user_review'),
            models.Index(fields=['user', '-created_at'], name='idx_user_created'),
            GinIndex(fields=['search_vector'], name='idx_search_vector'),
        ]
    
    def __str__(self):
        return f"{self.get_type_display()} - {self.user.username} - {self.created_at.date()}"
    
    def get_text_content(self):
        """Extract searchable text from content JSON"""
        text_parts = []
        if 'text' in self.content:
            text_parts.append(self.content['text'])
        if 'translation' in self.content:
            text_parts.append(self.content['translation'])
        if 'transcription' in self.content:
            text_parts.append(self.content['transcription'])
        return ' '.join(text_parts)


class Collection(models.Model):
    """User-created collections to organize items"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collections')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon identifier")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    item_count = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'collections'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='idx_collection_user'),
        ]
        unique_together = [['user', 'name']]
    
    def __str__(self):
        return f"{self.name} ({self.user.username})"
    
    def update_item_count(self):
        """Update the cached item count"""
        self.item_count = self.collection_items.count()
        self.save(update_fields=['item_count'])


class CollectionItem(models.Model):
    """Junction table for items in collections with ordering"""
    
    collection = models.ForeignKey(
        Collection, 
        on_delete=models.CASCADE, 
        related_name='collection_items'
    )
    item = models.ForeignKey(
        SavedItem, 
        on_delete=models.CASCADE, 
        related_name='in_collections'
    )
    position = models.IntegerField()
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'collection_items'
        ordering = ['position']
        unique_together = [['collection', 'item']]
        indexes = [
            models.Index(fields=['collection', 'position'], name='idx_collection_pos'),
        ]
    
    def __str__(self):
        return f"{self.collection.name} - {self.item.id}"


class StudySession(models.Model):
    """Track user study sessions for analytics"""
    
    SESSION_TYPES = [
        ('flashcard', 'Flashcard Review'),
        ('pronunciation_practice', 'Pronunciation Practice'),
        ('vocabulary_review', 'Vocabulary Review'),
        ('mixed', 'Mixed Practice'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_sessions')
    session_type = models.CharField(max_length=30, choices=SESSION_TYPES)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    items_reviewed = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'study_sessions'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', '-started_at'], name='idx_session_user'),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.get_session_type_display()} - {self.started_at.date()}"
    
    @property
    def duration_minutes(self):
        """Calculate session duration in minutes"""
        if self.ended_at:
            delta = self.ended_at - self.started_at
            return round(delta.total_seconds() / 60, 2)
        return None


class ItemReview(models.Model):
    """Detailed tracking of individual item reviews"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(
        SavedItem, 
        on_delete=models.CASCADE, 
        related_name='reviews'
    )
    session = models.ForeignKey(
        StudySession, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='item_reviews'
    )
    reviewed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # SM-2 algorithm quality rating (0-5)
    quality = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text="0=complete blackout, 5=perfect response"
    )
    
    time_spent_seconds = models.IntegerField(null=True, blank=True)
    was_correct = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'item_reviews'
        ordering = ['-reviewed_at']
        indexes = [
            models.Index(fields=['item', '-reviewed_at'], name='idx_review_item'),
            models.Index(fields=['session'], name='idx_review_session'),
        ]
    
    def __str__(self):
        return f"Review: {self.item.id} - Q{self.quality} - {self.reviewed_at.date()}"
    

class UserStorageQuota(models.Model):
    """Track user's audio storage usage with both size and count limits"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='storage_quota')
    
    # Storage-based limits (in bytes)
    used_bytes = models.BigIntegerField(default=0, help_text="Total bytes used by user")
    quota_bytes = models.BigIntegerField(default=104857600, help_text="Storage quota in bytes (default 100MB)")
    
    # Count-based limits
    audio_file_count = models.PositiveSmallIntegerField(default=0)
    max_audio_files = models.PositiveSmallIntegerField(default=50, help_text="Maximum number of audio files")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_storage_quota'
        indexes = [
            models.Index(fields=['user'], name='idx_storage_user'),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.used_mb:.2f}MB / {self.quota_mb}MB"
    
    @property
    def used_mb(self):
        """Convert bytes to MB for display"""
        return self.used_bytes / (1024 * 1024)
    
    @property
    def quota_mb(self):
        """Convert quota bytes to MB for display"""
        return self.quota_bytes / (1024 * 1024)
    
    @property
    def remaining_bytes(self):
        """Calculate remaining storage"""
        return max(0, self.quota_bytes - self.used_bytes)
    
    @property
    def remaining_mb(self):
        """Remaining storage in MB"""
        return self.remaining_bytes / (1024 * 1024)
    
    @property
    def usage_percentage(self):
        """Calculate usage percentage"""
        if self.quota_bytes == 0:
            return 0
        return (self.used_bytes / self.quota_bytes) * 100
    
    def can_upload(self, file_size_bytes):
        """Check if user can upload a file of given size"""
        space_available = self.remaining_bytes >= file_size_bytes
        count_available = self.audio_file_count < self.max_audio_files
        return space_available and count_available
    
    def add_file(self, file_size_bytes):
        """Add a file to user's usage"""
        self.used_bytes += file_size_bytes
        self.audio_file_count += 1
        self.save(update_fields=['used_bytes', 'audio_file_count', 'updated_at'])
    
    def remove_file(self, file_size_bytes):
        """Remove a file from user's usage"""
        self.used_bytes = max(0, self.used_bytes - file_size_bytes)
        self.audio_file_count = max(0, self.audio_file_count - 1)
        self.save(update_fields=['used_bytes', 'audio_file_count', 'updated_at'])