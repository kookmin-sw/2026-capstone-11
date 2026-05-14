using UnityEngine;
using DG.Tweening;

namespace Animations
{
    public class CardAnimator : MonoBehaviour
    {
        [SerializeField] private RectTransform visualRoot;

        [SerializeField] private Animator animator;
        [SerializeField] private Canvas sortingCanvas;

        [Header("Offset")]
        [SerializeField] private float selectedY = 30f;

        [SerializeField] private float selectedScale = 1.05f;

        [SerializeField] private float duration = 0.15f;

        private Tween moveTween;
        private Tween scaleTween;

        private bool isSelected;

        public void SetSelected(bool selected)
        {
            if (isSelected == selected)
                return;

            isSelected = selected;

            PlaySelectionAnimation(selected);
        }

        private void PlaySelectionAnimation(bool selected)
        {
            moveTween?.Kill();
            scaleTween?.Kill();

            float targetY = selected ? selectedY : 0f;
            float targetScale = selected ? selectedScale : 1f;
            
            sortingCanvas.sortingOrder = selected ? 1 : 0;

            moveTween = visualRoot
                .DOLocalMoveY(targetY, duration)
                .SetEase(Ease.OutQuad);

            scaleTween = visualRoot
                .DOScale(targetScale, duration)
                .SetEase(Ease.OutQuad);
        }

        // TODO: 추후 애니메이션 구현 시 활용
        public void PlayDraw()
        {
            animator.Play("Draw");
        }

        public void PlayUse()
        {
            animator.Play("Use");
        }

        public void PlayFlash()
        {
            animator.Play("Flash");
        }
    }
}