using UnityEngine;
using core.Sound;
using Title.UI;

public class TitleBotstrap : MonoBehaviour
{
    [SerializeField] private SoundManager soundManager;
    [SerializeField] private PlayFabAccountManager accountManager;
    [SerializeField] private PlayFabAccountUI accountUI;
    [SerializeField] private TitleInputController uiController;

    void Start()
    {
        soundManager.Init();
        accountManager.Init();
        accountUI.Init();
        uiController.Init();

        SoundManager.Instance.StopBgm();
        SoundManager.Instance.PlayBgm(BgmKey.Title);
    }
}
