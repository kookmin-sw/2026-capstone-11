using UnityEngine;
using UnityEngine.UI;
using TMPro;
using entity.targetable;

namespace ui.tooltip
{
    public class TooltipEntity : MonoBehaviour
    {
        [SerializeField] private TMP_Text title;
        [SerializeField] private TMP_Text header;
        [SerializeField] private TMP_Text description;

        [SerializeField] private LayoutGroup layoutGroup;
        [SerializeField] private Vector2 offset = new Vector2(20f, -20f);

        private RectTransform rect;
        private Canvas canvas;
        private Camera cam;

        private void Awake()
        {
            rect = transform as RectTransform;
            canvas = GetComponentInParent<Canvas>();
            cam = canvas.worldCamera; // Screen Space - Camera 기준
        }

        public void Show(TooltipData data)
        {
            gameObject.SetActive(true);

            title.text = data.title;
            header.text = data.header;
            description.text = data.description;

            LayoutRebuilder.ForceRebuildLayoutImmediate(rect);
        }

        public void Hide()
        {
            gameObject.SetActive(false);
        }

        private void Update()
        {
            if (!gameObject.activeSelf) return;

            UpdatePosition();
        }

        private void UpdatePosition()
        {
            Vector2 mouse = Input.mousePosition;

            RectTransformUtility.ScreenPointToLocalPointInRectangle(
                canvas.transform as RectTransform,
                mouse,
                cam,
                out Vector2 local
            );

            float width = rect.rect.width;
            float height = rect.rect.height;

            Vector2 pos = local + offset;

            // 방향 전환
            if (mouse.x + width > Screen.width)
                pos.x = local.x - width - offset.x;

            if (mouse.y - height < 0)
                pos.y = local.y + height + offset.y;

            // clamp
            var canvasRect = canvas.transform as RectTransform;
            float cw = canvasRect.rect.width;
            float ch = canvasRect.rect.height;

            pos.x = Mathf.Clamp(pos.x, -cw / 2, cw / 2 - width);
            pos.y = Mathf.Clamp(pos.y, -ch / 2 + height, ch / 2);

            rect.localPosition = pos;
        }
    }
}