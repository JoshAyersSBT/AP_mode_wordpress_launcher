document.addEventListener('DOMContentLoaded', () => {
  const links = document.querySelectorAll('.lesson-list a');
  links.forEach(link => {
    link.addEventListener('click', () => {
      localStorage.setItem('lastLesson', link.getAttribute('href'));
    });
  });

  const lastLesson = localStorage.getItem('lastLesson');
  if (lastLesson) {
    const resumeLink = document.createElement('a');
    resumeLink.href = lastLesson;
    resumeLink.textContent = 'Resume Last Lesson';
    resumeLink.className = 'resume-link';
    document.body.appendChild(resumeLink);
  }
});
