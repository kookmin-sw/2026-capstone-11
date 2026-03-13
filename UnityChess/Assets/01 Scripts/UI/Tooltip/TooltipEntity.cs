using UnityEngine;
using UnityEngine.UI;
using TMPro;
using entity.targetable;

namespace ui.tooltip
{
    /// <summary>
    /// 툴팁 UI 엔티티 클래스
    /// </summary>
    public class TooltipEntity : MonoBehaviour
    {
        // 툴팁 UI의 텍스트 컴포넌트
        [SerializeField] TMP_Text title;
        [SerializeField] TMP_Text header;
        [SerializeField] TMP_Text description;

        // 툴팁의 UI 레이아웃 컴포넌트
        [SerializeField] LayoutGroup layoutGroup;

        // 툴팁이 마우스를 따라다닐 때의 오프셋
        [SerializeField] Vector2 offset; 


        public void SetData(TooltipData data)
        {
            title.text = data.title;
            header.text = data.header;
            description.text = data.description;

            LayoutRebuilder.ForceRebuildLayoutImmediate(
                transform as RectTransform
            );
        }

        public void Show(TooltipData tooltipData)
        {
            gameObject.SetActive(true);

            SetData(tooltipData);

            // 툴팁 크기에 맞게 오프셋 조정
            offset += new Vector2(
                layoutGroup.preferredWidth / 4,
                -layoutGroup.preferredHeight / 2
            );
        }

        public void Hide()
        {
            gameObject.SetActive(false);
        }

        void Update()
        {
            transform.position = Input.mousePosition + (Vector3) offset;
        }

        // 테스트용
        void Start()
        {
            Show(new TooltipData
            {
                title = "테스트 유닛",
                header = "[클래스: 룩]",
                description = "공격력: 1 체력: 3\n[턴 시작] 테스트 능력: 아무 일도 일어나지 않습니다.\n배치/이동 코스트: 1"
            });
        }
    }
}
