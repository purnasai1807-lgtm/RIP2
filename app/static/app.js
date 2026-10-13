document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });
  const dependencyKind = document.getElementById('dep-kind');
  if (dependencyKind) {
    const syncDependencyTarget = () => {
      const resourceTarget = document.getElementById('dep-target-resource');
      const activityTarget = document.getElementById('dep-target-activity');
      const useResource = dependencyKind.value === 'resource';
      resourceTarget.hidden = !useResource;
      resourceTarget.disabled = !useResource;
      activityTarget.hidden = useResource;
      activityTarget.disabled = useResource;
    };
    dependencyKind.addEventListener('change', syncDependencyTarget);
    syncDependencyTarget();
  }
  document.querySelectorAll('input, textarea, select').forEach((field) => {
    field.addEventListener('input', () => field.classList.remove('invalid'));
  });
});
